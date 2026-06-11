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
    query_base = """
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
            LEAD(close, 5) OVER(PARTITION BY stock_code ORDER BY date) as close_d5
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '2023-10-01'
    )
    SELECT 
        p.date, p.stock_code, nt.stock_name, nt.theme_name, g.grade,
        p.histogram, p.phase,
        v1.close, v1.close_d5
    FROM theme_phase_classification p
    JOIN industry.theme_name_list nt ON p.stock_code = nt.stock_code
    JOIN theme_grades g ON nt.theme_name = g.theme_name AND p.date = g.date
    JOIN price_data v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    ORDER BY p.stock_code, p.date
    """
    
    print("Connecting to DB and extracting base data...")
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    df = pd.read_sql(query_base, conn)
    
    print("Extracting DWM OHLCV data for Volume Analysis...")
    query_dwm = """
    SELECT stock_code, d_date, d_volume, w_open, w_high, w_low, w_close, w_avg_volume 
    FROM visual.vsl_dwm_ohlcv 
    WHERE d_date >= '2024-06-01'
    """
    dwm_df = pd.read_sql(query_dwm, conn)
    conn.close()
    
    # Calculate Daily Volume Ratio (vs past 20 days)
    dwm_df = dwm_df.sort_values(['stock_code', 'd_date'])
    dwm_df['d_vol_ma20'] = dwm_df.groupby('stock_code')['d_volume'].transform(lambda x: x.shift(1).rolling(20).mean())
    dwm_df['vol_ratio'] = dwm_df['d_volume'] / dwm_df['d_vol_ma20']
    
    # Calculate Weekly Avg Volume Ratio (vs past 4 weeks)
    # Using w_avg_volume to represent weekly volume activity
    dwm_df['w_avg_vol_ma4'] = dwm_df.groupby('stock_code')['w_avg_volume'].transform(lambda x: x.shift(1).rolling(20).mean()) # 20 days ~ 4 weeks
    dwm_df['w_vol_ratio'] = dwm_df['w_avg_volume'] / dwm_df['w_avg_vol_ma4']
    
    print("Calculating Cycles (V-shape Extrema)...")
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    df['prev_hist'] = df.groupby('stock_code')['histogram'].shift(1)
    df['prev2_hist'] = df.groupby('stock_code')['histogram'].shift(2)
    
    df['is_neg_max'] = (df['prev_phase'] == 2) & (df['phase'] == 1) & (df['prev_z'] <= -1.0) & (df['prev2_hist'] > df['prev_hist'])
    df['is_pos_max'] = (df['prev_phase'] == 3) & (df['phase'] == 4) & (df['prev_z'] >= 1.0) & (df['prev2_hist'] < df['prev_hist'])
    
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
    
    valid_seq = valid_seq[valid_seq['next_next_date'] >= pd.to_datetime('2025-01-01').date()]
    
    point_c = df[['stock_code', 'theme_name', 'date', 'grade', 'close', 'close_d5']].copy()
    point_c['date'] = pd.to_datetime(point_c['date']).dt.date
    
    merged = pd.merge(
        valid_seq[['stock_code', 'stock_name', 'next_next_date']],
        point_c,
        left_on=['stock_code', 'next_next_date'], right_on=['stock_code', 'date'],
        how='inner'
    )
    
    dwm_df['d_date'] = pd.to_datetime(dwm_df['d_date']).dt.date
    target_df = pd.merge(
        merged, dwm_df,
        left_on=['stock_code', 'date'], right_on=['stock_code', 'd_date'],
        how='left'
    )
    
    target_df = target_df.dropna(subset=['close_d5', 'w_close', 'vol_ratio'])
    
    # Filter: 6 Grade
    target_df = target_df[target_df['grade'] == '6등급']
    
    # Filter: Golden Hammer
    target_df['body'] = np.maximum(abs(target_df['w_close'] - target_df['w_open']), target_df['w_open'] * 0.0001)
    target_df['upper_tail'] = target_df['w_high'] - target_df[['w_open', 'w_close']].max(axis=1)
    target_df['lower_tail'] = target_df[['w_open', 'w_close']].min(axis=1) - target_df['w_low']
    
    target_df = target_df[(target_df['lower_tail'] / target_df['body'] >= 3.0) & (target_df['upper_tail'] / target_df['body'] <= 1.0)]
    
    target_df['ret_5d'] = (target_df['close_d5'] - target_df['close']) / target_df['close'] * 100
    
    win_group = target_df[target_df['ret_5d'] > 0]
    loss_group = target_df[target_df['ret_5d'] <= 0]
    
    print("\n========================================================")
    print("🔥 [6등급 + 황금 망치형] 수익/손실 그룹 거래량 폭증 비교")
    print("========================================================\n")
    
    def print_volume_stats(group_df, name):
        count = len(group_df)
        if count == 0: return
        
        avg_vol_ratio = group_df['vol_ratio'].mean()
        med_vol_ratio = group_df['vol_ratio'].median()
        
        avg_w_vol_ratio = group_df['w_vol_ratio'].mean()
        med_w_vol_ratio = group_df['w_vol_ratio'].median()
        
        # Distribution of Daily Volume Spikes
        spike_2x = (group_df['vol_ratio'] >= 2.0).mean() * 100
        spike_5x = (group_df['vol_ratio'] >= 5.0).mean() * 100
        
        print(f"🟢 [{name} 그룹] - 총 {count}건")
        print(f"  [1] 일일 거래량 폭증 (Point C 당일 거래량 / 과거 20일 평균)")
        print(f"      - 평균 폭증 배수: {avg_vol_ratio:.2f}배")
        print(f"      - 중앙값 배수: {med_vol_ratio:.2f}배")
        print(f"      - 평소 대비 2배 이상 터진 비율: {spike_2x:.1f}%")
        print(f"      - 평소 대비 5배 이상 터진 비율: {spike_5x:.1f}%")
        print(f"  [2] 주간 평균 거래량 폭증 (해당 주간 / 과거 4주 평균)")
        print(f"      - 평균 폭증 배수: {avg_w_vol_ratio:.2f}배")
        print(f"      - 중앙값 배수: {med_w_vol_ratio:.2f}배")
        print("\n")

    print_volume_stats(win_group, "수익(Win)")
    print_volume_stats(loss_group, "손실(Loss)")

if __name__ == "__main__":
    main()
