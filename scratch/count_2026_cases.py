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
    , price_data AS (
        SELECT 
            date, stock_code, close,
            LEAD(close, 5) OVER(PARTITION BY stock_code ORDER BY date) as close_plus_5d
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '2023-10-01'
    )
    SELECT 
        p.date, p.stock_code, nt.theme_name, g.grade,
        p.histogram, p.phase,
        v1.close, v1.close_plus_5d
    FROM theme_phase_classification p
    JOIN industry.theme_name_list nt ON p.stock_code = nt.stock_code
    JOIN theme_grades g ON nt.theme_name = g.theme_name AND p.date = g.date
    JOIN price_data v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    ORDER BY p.stock_code, p.date
    """
    
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    
    df['is_neg_max'] = (df['prev_phase'] == 2) & (df['phase'] == 1) & (df['prev_z'] <= -1.0)
    df['is_pos_max'] = (df['prev_phase'] == 3) & (df['phase'] == 4) & (df['prev_z'] >= 1.0)
    
    extrema = df[df['is_neg_max'] | df['is_pos_max']].copy()
    extrema = extrema.sort_values(['stock_code', 'date'])
    extrema['type'] = np.where(extrema['is_neg_max'], -1, 1)
    
    extrema['next_type'] = extrema.groupby('stock_code')['type'].shift(-1)
    extrema['next_date'] = extrema.groupby('stock_code')['date'].shift(-1)
    extrema['next_next_type'] = extrema.groupby('stock_code')['type'].shift(-2)
    extrema['next_next_date'] = extrema.groupby('stock_code')['date'].shift(-2)
    
    valid_seq = extrema[(extrema['type'] == -1) & (extrema['next_type'] == 1) & (extrema['next_next_type'] == -1)].copy()
    valid_seq = valid_seq.dropna(subset=['next_next_date'])
    valid_seq['next_next_date'] = pd.to_datetime(valid_seq['next_next_date']).dt.date
    valid_seq['next_date'] = pd.to_datetime(valid_seq['next_date']).dt.date
    
    # Filter 2026-01-01 onwards based on Point C (next_next_date)
    valid_seq = valid_seq[valid_seq['next_next_date'] >= pd.to_datetime('2026-01-01').date()]
    
    point_a = valid_seq[['stock_code', 'theme_name', 'date', 'close', 'next_date', 'next_next_date']].rename(
        columns={'date': 'date_A', 'close': 'close_A', 'next_date': 'date_B', 'next_next_date': 'date_C'}
    )
    
    df['date'] = pd.to_datetime(df['date']).dt.date
    point_c = df[['stock_code', 'theme_name', 'date', 'grade', 'close', 'close_plus_5d']].rename(
        columns={'date': 'date_C', 'close': 'close_C', 'grade': 'grade_C'}
    )
    
    merged = pd.merge(point_a, point_c, on=['stock_code', 'theme_name', 'date_C'], how='inner')
    
    merged['diff_AC_pct'] = (merged['close_C'] - merged['close_A']) / merged['close_A'] * 100
    
    # Filter: Grade 6 and Diff <= -5%
    target_df = merged[(merged['grade_C'] == '6등급') & (merged['diff_AC_pct'] <= -5.0)].copy()
    
    # 5d return
    target_df['return_5d_pct'] = (target_df['close_plus_5d'] - target_df['close_C']) / target_df['close_C'] * 100
    # Drop rows without 5d return (too recent)
    target_df = target_df.dropna(subset=['return_5d_pct'])
    
    unique_stocks = target_df['stock_code'].nunique()
    total_events = len(target_df)
    avg_return_5d = target_df['return_5d_pct'].mean()
    
    print(f"===========================================================")
    print(f"2026년 1월 1일 이후 발굴된 건수 (5일 경과 완료건): 총 {total_events}건")
    print(f"2026년 1월 1일 이후 발굴된 유니크 종목 수: {unique_stocks}종목")
    print(f"★ 5일 후 평균 수익률: {avg_return_5d:.2f}%")
    print(f"===========================================================\n")
    
    recent = target_df.sort_values('date_C', ascending=False).head(10)
    print("[가장 최근 발굴된 10건 세부 내역]")
    for _, row in recent.iterrows():
        print(f"- 종목코드: {row['stock_code']} | 테마: {row['theme_name']}")
        print(f"  [일자] Point A: {row['date_A']} -> Point B: {row['date_B']} -> Point C: {row['date_C']}")
        print(f"  [수익] Point A 대비 하락률: {row['diff_AC_pct']:.2f}%  | ★ 5일 후 수익률: {row['return_5d_pct']:.2f}%\n")

if __name__ == "__main__":
    main()
