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
    , price_data AS (
        SELECT 
            date, stock_code, close,
            LEAD(close, 5) OVER(PARTITION BY stock_code ORDER BY date) as close_d5
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '2023-10-01'
    )
    SELECT 
        p.date, p.stock_code,
        p.histogram, p.phase,
        v1.close, v1.close_d5
    FROM theme_phase_classification p
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
    
    print("Extracting DWM OHLCV data...")
    query_dwm = """
    SELECT stock_code, d_date, w_open, w_high, w_low, w_close 
    FROM visual.vsl_dwm_ohlcv 
    WHERE d_date >= '2024-10-01'
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
    
    point_c = df[['stock_code', 'date', 'close', 'close_d5']].copy()
    point_c['date'] = pd.to_datetime(point_c['date']).dt.date
    
    target_df = pd.merge(
        valid_seq[['stock_code', 'next_next_date']],
        point_c,
        left_on=['stock_code', 'next_next_date'], right_on=['stock_code', 'date'],
        how='inner'
    )
    
    dwm_df['d_date'] = pd.to_datetime(dwm_df['d_date']).dt.date
    target_df = pd.merge(
        target_df, dwm_df,
        left_on=['stock_code', 'date'], right_on=['stock_code', 'd_date'],
        how='left'
    )
    
    target_df['ret_5d'] = (target_df['close_d5'] - target_df['close']) / target_df['close'] * 100
    target_df = target_df.dropna(subset=['ret_5d', 'w_close'])
    
    # Calculate body and tails
    # Add epsilon to body to avoid division by zero (e.g. 0.0001)
    target_df['body'] = np.maximum(abs(target_df['w_close'] - target_df['w_open']), target_df['w_open'] * 0.001)
    target_df['upper_tail'] = target_df['w_high'] - target_df[['w_open', 'w_close']].max(axis=1)
    target_df['lower_tail'] = target_df[['w_open', 'w_close']].min(axis=1) - target_df['w_low']
    
    target_df['lower_ratio'] = target_df['lower_tail'] / target_df['body']
    target_df['upper_ratio'] = target_df['upper_tail'] / target_df['body']
    
    print(f"Total Base Population: {len(target_df)}")
    
    lower_tests = [0.0, 1.0, 1.5, 2.0, 3.0]
    upper_tests = [100.0, 1.0, 0.5, 0.2] # 100 means no restriction
    
    results = []
    
    for l_val in lower_tests:
        for u_val in upper_tests:
            subset = target_df[(target_df['lower_ratio'] >= l_val) & (target_df['upper_ratio'] <= u_val)]
            count = len(subset)
            if count < 10: # ignore statistically insignificant samples
                continue
            
            win_rate = (subset['ret_5d'] > 0).mean() * 100
            avg_ret = subset['ret_5d'].mean()
            median_ret = subset['ret_5d'].median()
            
            results.append({
                'lower_ratio_min': l_val,
                'upper_ratio_max': u_val,
                'count': count,
                'win_rate': win_rate,
                'avg_ret': avg_ret,
                'median_ret': median_ret
            })
            
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values('avg_ret', ascending=False)
    
    print("\n=========================================================================")
    print("📈 주봉 캔들 파라미터 (아랫수염 vs 윗수염 비율) 백테스트 결과 (수익률 순)")
    print("=========================================================================")
    for i, row in res_df.iterrows():
        l_cond = f"아랫수염 >= 몸통 {row['lower_ratio_min']}배"
        u_cond = f"윗수염 <= 몸통 {row['upper_ratio_max']}배" if row['upper_ratio_max'] < 100 else "윗수염 제한없음"
        print(f"조건: [{l_cond}] AND [{u_cond}]")
        print(f" -> 발굴수: {row['count']:.0f}개 | 승률: {row['win_rate']:.1f}% | 평균수익률: {row['avg_ret']:.2f}% | 중앙값: {row['median_ret']:.2f}%\n")

if __name__ == "__main__":
    main()
