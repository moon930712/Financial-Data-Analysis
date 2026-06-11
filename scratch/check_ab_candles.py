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
    SELECT 
        p.date, p.stock_code,
        p.histogram, p.phase
    FROM theme_phase_classification p
    ORDER BY p.stock_code, p.date
    """
    
    print("Connecting to DB and extracting base data...")
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    df = pd.read_sql(query_base, conn)
    
    print("Extracting DWM OHLCV...")
    query_dwm = """
    SELECT stock_code, d_date, w_open, w_high, w_low, w_close 
    FROM visual.vsl_dwm_ohlcv 
    WHERE d_date >= '2023-10-01'
    """
    dwm_df = pd.read_sql(query_dwm, conn)
    conn.close()
    
    print("Calculating Cycles (V-shape Extrema)...")
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    df['prev_hist'] = df.groupby('stock_code')['histogram'].shift(1)
    df['prev2_hist'] = df.groupby('stock_code')['histogram'].shift(2)
    
    # V-shape Extrema
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
    
    valid_seq['date_A'] = pd.to_datetime(valid_seq['date']).dt.date
    valid_seq['date_B'] = pd.to_datetime(valid_seq['next_date']).dt.date
    valid_seq['date_C'] = pd.to_datetime(valid_seq['next_next_date']).dt.date
    
    # Filter for 2025-01-01 onwards (Point C)
    valid_seq = valid_seq[valid_seq['date_C'] >= pd.to_datetime('2025-01-01').date()]
    print(f"Found {len(valid_seq)} valid cycles since 2025-01-01.")
    
    dwm_df['d_date'] = pd.to_datetime(dwm_df['d_date']).dt.date
    
    # Merge for Point A
    df_A = pd.merge(
        valid_seq[['stock_code', 'date_A', 'date_B']], 
        dwm_df, 
        left_on=['stock_code', 'date_A'], right_on=['stock_code', 'd_date'], 
        how='inner'
    )
    df_A['candle_A'] = np.where(df_A['w_close'] >= df_A['w_open'], '양봉', '음봉')
    
    # Merge for Point B
    df_B = pd.merge(
        valid_seq[['stock_code', 'date_A', 'date_B']], 
        dwm_df, 
        left_on=['stock_code', 'date_B'], right_on=['stock_code', 'd_date'], 
        how='inner'
    )
    df_B['candle_B'] = np.where(df_B['w_close'] >= df_B['w_open'], '양봉', '음봉')
    
    print("\n================================================")
    print("Point A (바닥 타점) 주봉 캔들 분포:")
    dist_A = df_A['candle_A'].value_counts(normalize=True) * 100
    for k, v in dist_A.items(): print(f" - {k}: {v:.1f}%")
    
    print("\nPoint B (천장 타점) 주봉 캔들 분포:")
    dist_B = df_B['candle_B'].value_counts(normalize=True) * 100
    for k, v in dist_B.items(): print(f" - {k}: {v:.1f}%")
    print("================================================\n")

if __name__ == "__main__":
    main()
