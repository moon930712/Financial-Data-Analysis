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
    conn.close()
    
    print("Calculating Cycles (V-shape Extrema)...")
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    df['prev_hist'] = df.groupby('stock_code')['histogram'].shift(1)
    df['prev2_hist'] = df.groupby('stock_code')['histogram'].shift(2)
    
    # Point A / C
    df['is_neg_max'] = (df['prev_phase'] == 2) & (df['phase'] == 1) & (df['prev_z'] <= -1.0) & (df['prev2_hist'] > df['prev_hist'])
    # Point B
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
    
    valid_seq['date_A'] = pd.to_datetime(valid_seq['date'])
    valid_seq['date_B'] = pd.to_datetime(valid_seq['next_date'])
    valid_seq['date_C'] = pd.to_datetime(valid_seq['next_next_date'])
    
    valid_seq = valid_seq[valid_seq['date_C'] >= pd.to_datetime('2025-01-01')]
    
    # Get Prices for A, B, C
    df['date'] = pd.to_datetime(df['date'])
    price_lookup = df[['stock_code', 'date', 'close', 'close_d5']].set_index(['stock_code', 'date'])
    
    def get_price(row, col_date):
        try: return price_lookup.loc[(row['stock_code'], row[col_date]), 'close']
        except: return np.nan

    def get_d5_ret(row):
        try: 
            c = price_lookup.loc[(row['stock_code'], row['date_C']), 'close']
            c5 = price_lookup.loc[(row['stock_code'], row['date_C']), 'close_d5']
            return (c5 - c) / c * 100
        except: return np.nan

    valid_seq['price_A'] = valid_seq.apply(lambda row: get_price(row, 'date_A'), axis=1)
    valid_seq['price_B'] = valid_seq.apply(lambda row: get_price(row, 'date_B'), axis=1)
    valid_seq['price_C'] = valid_seq.apply(lambda row: get_price(row, 'date_C'), axis=1)
    valid_seq['ret_5d'] = valid_seq.apply(get_d5_ret, axis=1)
    
    valid_seq = valid_seq.dropna(subset=['price_A', 'price_B', 'price_C', 'ret_5d'])
    
    print(f"Total Cases Found for Wave Analysis: {len(valid_seq)}")
    
    # Calculate Wave Metrics
    # 1. Time Intervals (in days)
    valid_seq['days_AB'] = (valid_seq['date_B'] - valid_seq['date_A']).dt.days
    valid_seq['days_BC'] = (valid_seq['date_C'] - valid_seq['date_B']).dt.days
    valid_seq['time_ratio'] = valid_seq['days_AB'] / np.maximum(valid_seq['days_BC'], 1)
    
    # 2. Amplitudes (%)
    valid_seq['amp_AB'] = (valid_seq['price_B'] - valid_seq['price_A']) / valid_seq['price_A'] * 100
    valid_seq['amp_BC'] = (valid_seq['price_C'] - valid_seq['price_B']) / valid_seq['price_B'] * 100
    valid_seq['net_AC'] = (valid_seq['price_C'] - valid_seq['price_A']) / valid_seq['price_A'] * 100
    
    win_group = valid_seq[valid_seq['ret_5d'] > 0]
    loss_group = valid_seq[valid_seq['ret_5d'] <= 0]
    
    print("\n========================================================")
    print("🌊 A -> B -> C 파동(진폭 및 소요 기간) 수익/손실 그룹 비교")
    print("========================================================\n")
    
    def analyze_wave(group_df, name):
        count = len(group_df)
        if count == 0: return
        
        avg_days_AB = group_df['days_AB'].mean()
        avg_days_BC = group_df['days_BC'].mean()
        
        # Time Categories
        # Fast Drop: AB > BC (올라갈땐 천천히, 내려갈땐 빨리 -> 투매)
        # Slow Drop: AB < BC (빨리 오르고 천천히 내려감 -> 건강한 눌림)
        fast_drop = (group_df['days_AB'] > group_df['days_BC']).mean() * 100
        slow_drop = (group_df['days_AB'] < group_df['days_BC']).mean() * 100
        
        # Net AC (Higher Lows vs Lower Lows)
        higher_lows = (group_df['net_AC'] > 0).mean() * 100
        lower_lows = (group_df['net_AC'] <= 0).mean() * 100
        
        print(f"🟢 [{name} 파동] - 총 {count}건")
        print(f"  [1] 소요 기간 (Time Interval)")
        print(f"      - A ➔ B (상승 기간) 평균: {avg_days_AB:.1f}일")
        print(f"      - B ➔ C (하락 기간) 평균: {avg_days_BC:.1f}일")
        print(f"      - 💥 급락형 파동 비율 (올라간 기간 > 내려간 기간): {fast_drop:.1f}%")
        print(f"      - 📉 완만형 파동 비율 (올라간 기간 < 내려간 기간): {slow_drop:.1f}%")
        print(f"  [2] 진폭 및 저점 갱신 여부 (Amplitude & Net Drop)")
        print(f"      - A ➔ B (평균 상승폭): +{group_df['amp_AB'].mean():.1f}%")
        print(f"      - B ➔ C (평균 하락폭): {group_df['amp_BC'].mean():.1f}%")
        print(f"      - 📈 쌍바닥(저점 상승, Point C > Point A) 형성 비율: {higher_lows:.1f}%")
        print(f"      - 📉 하락추세(저점 갱신, Point C < Point A) 형성 비율: {lower_lows:.1f}%")
        print("\n")

    analyze_wave(win_group, "수익(Win)")
    analyze_wave(loss_group, "손실(Loss)")

if __name__ == "__main__":
    main()
