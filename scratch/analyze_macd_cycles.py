import os
import psycopg2
import pandas as pd
import numpy as np
import sys

sys.stdout.reconfigure(encoding='utf-8')

def load_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env_vars[k] = v
    except: pass
    return env_vars

def main():
    print("Connecting to DB and extracting data...")
    query = """
    WITH all_valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2023-10-01' 
    )
    , theme_histo_base AS (
        SELECT 
            m.date
            , m.stock_code
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date IN (SELECT date FROM all_valid_dates)
    )
    , theme_phase_classification AS (
        SELECT 
            date
            , stock_code
            , histogram
            , CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN 1 
                WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 
                WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 
                ELSE 4 
              END as phase
        FROM theme_histo_base
    )
    , theme_aggregation AS (
        SELECT 
            nt.theme_name
            , p.date
            , COUNT(*) as total_cnt
            , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
            , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt
            , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt
            , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
            , COALESCE(SUM(v1.trade_value), 0) / COUNT(*) AS avg_trade_value
        FROM industry.theme_name_list nt
        INNER JOIN theme_phase_classification p ON nt.stock_code = p.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
        WHERE v1.close > 1000 
        GROUP BY nt.theme_name, p.date
        HAVING COUNT(*) >= 5
    )
    , final_ranking AS (
        SELECT date, theme_name
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                total_cnt DESC
              ) AS global_rank
        FROM theme_aggregation
    )
    , theme_grades AS (
        SELECT 
            date, theme_name
            , CASE 
                WHEN global_rank <= 25 THEN '1등급' 
                WHEN global_rank <= 50 THEN '2등급' 
                WHEN global_rank <= 75 THEN '3등급' 
                WHEN global_rank <= 100 THEN '4등급' 
                WHEN global_rank <= 125 THEN '5등급' 
                ELSE '6등급' 
              END AS grade
        FROM final_ranking
    )
    SELECT 
        p.date, p.stock_code, nt.theme_name, g.grade,
        p.histogram, p.phase,
        v1.close
    FROM theme_phase_classification p
    JOIN industry.theme_name_list nt ON p.stock_code = nt.stock_code
    JOIN theme_grades g ON nt.theme_name = g.theme_name AND p.date = g.date
    JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    ORDER BY p.stock_code, p.date
    """
    
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"Data fetched: {len(df)} rows.")
    
    # Calculate Z-score (60-day rolling)
    print("Calculating Z-scores...")
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    
    # Z-score thresholds
    Z_NEG_THRESH = -1.0
    Z_POS_THRESH = 1.0
    
    print("Finding true extrema...")
    df['is_neg_max'] = (df['prev_phase'] == 2) & (df['phase'] == 1) & (df['prev_z'] <= Z_NEG_THRESH)
    df['is_pos_max'] = (df['prev_phase'] == 3) & (df['phase'] == 4) & (df['prev_z'] >= Z_POS_THRESH)
    
    extrema = df[df['is_neg_max'] | df['is_pos_max']].copy()
    extrema = extrema.sort_values(['stock_code', 'date'])
    extrema['type'] = np.where(extrema['is_neg_max'], -1, 1)
    
    # Find sequence: -1, 1, -1
    extrema['next_type'] = extrema.groupby('stock_code')['type'].shift(-1)
    extrema['next_next_type'] = extrema.groupby('stock_code')['type'].shift(-2)
    extrema['next_next_date'] = extrema.groupby('stock_code')['date'].shift(-2)
    
    # Valid sequences
    valid_seq = extrema[(extrema['type'] == -1) & (extrema['next_type'] == 1) & (extrema['next_next_type'] == -1)].copy()
    valid_seq = valid_seq.dropna(subset=['next_next_date'])
    
    # We only consider cycles completed after 2024-01-01 (allowing previous months for the cycle to form)
    valid_seq = valid_seq[valid_seq['next_next_date'] >= pd.to_datetime('2024-01-01').date()]
    
    print(f"Found {len(valid_seq)} valid cycles (Negative -> Positive -> Negative).")
    
    # Merge back to get the Target Day (Point C) stats
    target_dates = valid_seq[['stock_code', 'next_next_date', 'theme_name']].rename(columns={'next_next_date': 'date'})
    target_dates['date'] = pd.to_datetime(target_dates['date'])
    df['date'] = pd.to_datetime(df['date'])
    
    result_df = pd.merge(target_dates, df, on=['stock_code', 'date', 'theme_name'], how='inner')
    
    print("\n=== MACD 사이클 (음수맥스->양수맥스->음수맥스) 도달 시점(Point C)의 테마 등급 분포 ===")
    grade_counts = result_df['grade'].value_counts()
    for g, c in grade_counts.items():
        print(f"  {g}: {c}건 ({c/len(result_df)*100:.1f}%)")
        
    print("\n=== 타겟 시점(Point C) 전후 주가 추이 (Price Action) ===")
    # Calculate price change around D-Day
    # We will get D-2, D-1, D0, D+1 prices. 
    # To do this efficiently, we shift prices per stock
    df['close_d_minus_2'] = df.groupby('stock_code')['close'].shift(2)
    df['close_d_minus_1'] = df.groupby('stock_code')['close'].shift(1)
    df['close_d0'] = df['close']
    df['close_d_plus_1'] = df.groupby('stock_code')['close'].shift(-1)
    
    price_df = pd.merge(target_dates, df[['stock_code', 'date', 'close_d_minus_2', 'close_d_minus_1', 'close_d0', 'close_d_plus_1']], on=['stock_code', 'date'], how='inner')
    
    # Calculate daily return %
    price_df['ret_d_minus_1'] = (price_df['close_d_minus_1'] - price_df['close_d_minus_2']) / price_df['close_d_minus_2'] * 100
    price_df['ret_d0'] = (price_df['close_d0'] - price_df['close_d_minus_1']) / price_df['close_d_minus_1'] * 100
    price_df['ret_d_plus_1'] = (price_df['close_d_plus_1'] - price_df['close_d0']) / price_df['close_d0'] * 100
    
    print(f"  D-1 (전일) 평균 상승률: {price_df['ret_d_minus_1'].mean():.2f}%")
    print(f"  D-Day (당일) 평균 상승률: {price_df['ret_d0'].mean():.2f}%")
    print(f"  D+1 (다음날) 평균 상승률: {price_df['ret_d_plus_1'].mean():.2f}%")
    
    # Win rate (how often is it positive)
    print(f"  D-1 상승 종목 비율: {(price_df['ret_d_minus_1'] > 0).mean()*100:.1f}%")
    print(f"  D-Day 상승 종목 비율: {(price_df['ret_d0'] > 0).mean()*100:.1f}%")
    print(f"  D+1 상승 종목 비율: {(price_df['ret_d_plus_1'] > 0).mean()*100:.1f}%")

    # Let's break down price action by Grade on D-Day
    for grade in ['1등급', '2등급', '6등급']:
        sub = pd.merge(target_dates, df[['stock_code', 'date', 'grade', 'close_d_minus_2', 'close_d_minus_1', 'close_d0', 'close_d_plus_1']], on=['stock_code', 'date'], how='inner')
        sub = sub[sub['grade'] == grade]
        if sub.empty: continue
        sub['ret_d0'] = (sub['close_d0'] - sub['close_d_minus_1']) / sub['close_d_minus_1'] * 100
        sub['ret_d_plus_1'] = (sub['close_d_plus_1'] - sub['close_d0']) / sub['close_d0'] * 100
        print(f"\n[{grade} 달성 케이스 Price Action]")
        print(f"  D-Day 상승률: {sub['ret_d0'].mean():.2f}% (승률: {(sub['ret_d0'] > 0).mean()*100:.1f}%)")
        print(f"  D+1 상승률: {sub['ret_d_plus_1'].mean():.2f}% (승률: {(sub['ret_d_plus_1'] > 0).mean()*100:.1f}%)")

if __name__ == "__main__":
    main()
