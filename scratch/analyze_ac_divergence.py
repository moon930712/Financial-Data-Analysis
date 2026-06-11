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
    
    print("Calculating Cycles and MACD Depths...")
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    df['prev_hist'] = df.groupby('stock_code')['histogram'].shift(1)
    df['prev2_hist'] = df.groupby('stock_code')['histogram'].shift(2)
    
    # Extract MACD valley depth (the absolute value of prev_hist which is the lowest point before turning up)
    df['valley_depth'] = df['prev_hist'].abs()
    
    # Point A / C condition
    df['is_neg_max'] = (df['prev_phase'] == 2) & (df['phase'] == 1) & (df['prev_z'] <= -1.0) & (df['prev2_hist'] > df['prev_hist'])
    # Point B condition
    df['is_pos_max'] = (df['prev_phase'] == 3) & (df['phase'] == 4) & (df['prev_z'] >= 1.0) & (df['prev2_hist'] < df['prev_hist'])
    
    extrema = df[df['is_neg_max'] | df['is_pos_max']].copy()
    extrema = extrema.sort_values(['stock_code', 'date'])
    extrema['type'] = np.where(extrema['is_neg_max'], -1, 1)
    
    extrema['next_type'] = extrema.groupby('stock_code')['type'].shift(-1)
    extrema['next_date'] = extrema.groupby('stock_code')['date'].shift(-1)
    extrema['next_next_type'] = extrema.groupby('stock_code')['type'].shift(-2)
    extrema['next_next_date'] = extrema.groupby('stock_code')['date'].shift(-2)
    
    # Valid A -> B -> C sequence
    valid_seq = extrema[(extrema['type'] == -1) & (extrema['next_type'] == 1) & (extrema['next_next_type'] == -1)].copy()
    valid_seq = valid_seq.dropna(subset=['next_next_date'])
    
    valid_seq['date_A'] = pd.to_datetime(valid_seq['date'])
    valid_seq['date_B'] = pd.to_datetime(valid_seq['next_date'])
    valid_seq['date_C'] = pd.to_datetime(valid_seq['next_next_date'])
    
    # Filter 2025 onwards (Point C)
    valid_seq = valid_seq[valid_seq['date_C'] >= pd.to_datetime('2025-01-01')]
    
    df['date'] = pd.to_datetime(df['date'])
    lookup_df = df.set_index(['stock_code', 'date'])
    
    print("Mapping Price and MACD Depth for Point A and C...")
    def get_features(row):
        try:
            a_data = lookup_df.loc[(row['stock_code'], row['date_A'])]
            c_data = lookup_df.loc[(row['stock_code'], row['date_C'])]
            
            return pd.Series({
                'price_A': a_data['close'],
                'macd_depth_A': a_data['valley_depth'],
                'price_C': c_data['close'],
                'macd_depth_C': c_data['valley_depth'],
                'ret_5d': (c_data['close_d5'] - c_data['close']) / c_data['close'] * 100
            })
        except:
            return pd.Series({ 'price_A': np.nan, 'macd_depth_A': np.nan, 'price_C': np.nan, 'macd_depth_C': np.nan, 'ret_5d': np.nan })

    features = valid_seq.apply(get_features, axis=1)
    valid_seq = pd.concat([valid_seq, features], axis=1)
    valid_seq = valid_seq.dropna(subset=['price_A', 'price_C', 'macd_depth_A', 'macd_depth_C', 'ret_5d'])
    
    # 4 Quadrants classification
    valid_seq['price_trend'] = np.where(valid_seq['price_C'] >= valid_seq['price_A'], '쌍바닥(가격상승)', '지하실(가격하락)')
    valid_seq['macd_trend'] = np.where(valid_seq['macd_depth_C'] < valid_seq['macd_depth_A'], '모멘텀약화(다이버전스)', '모멘텀강화(가속)')
    
    valid_seq['quadrant'] = valid_seq['price_trend'] + " + " + valid_seq['macd_trend']
    
    # Classify Quadrant Names
    conditions = [
        (valid_seq['price_trend'] == '쌍바닥(가격상승)') & (valid_seq['macd_trend'] == '모멘텀약화(다이버전스)'),
        (valid_seq['price_trend'] == '지하실(가격하락)') & (valid_seq['macd_trend'] == '모멘텀약화(다이버전스)'),
        (valid_seq['price_trend'] == '쌍바닥(가격상승)') & (valid_seq['macd_trend'] == '모멘텀강화(가속)'),
        (valid_seq['price_trend'] == '지하실(가격하락)') & (valid_seq['macd_trend'] == '모멘텀강화(가속)')
    ]
    choices = ['① 찐쌍바닥', '② 히든 다이버전스(언더슈팅)', '③ 약세 쌍바닥', '④ 완벽한 지하실']
    valid_seq['category'] = np.select(conditions, choices, default='Unknown')
    
    print("\n========================================================")
    print("🔍 Point A vs C 다이버전스(가격 & MACD 깊이) 분석 결과 (전체 등급 대상)")
    print("========================================================\n")
    
    total_cases = len(valid_seq)
    
    for cat in choices:
        sub = valid_seq[valid_seq['category'] == cat]
        count = len(sub)
        if count == 0: continue
        
        ratio = count / total_cases * 100
        win_rate = (sub['ret_5d'] > 0).mean() * 100
        avg_ret = sub['ret_5d'].mean()
        
        desc = ""
        if '①' in cat: desc = "Point C가 A보다 가격은 높고, MACD 골짜기는 얕아진 이상적인 상승 전환 (Higher Low + Divergence)"
        elif '②' in cat: desc = "Point C가 A보다 가격은 낮아져 지지선이 깨졌지만, MACD 골짜기가 얕아져 하락 에너지가 죽은 상태 (Lower Low + Divergence)"
        elif '③' in cat: desc = "Point C가 A보다 가격은 높지만, MACD 골짜기가 더 깊어져 하락 에너지가 빵빵한 가짜 반등 (Higher Low + Continuation)"
        elif '④' in cat: desc = "Point C가 A보다 가격도 낮고, MACD 골짜기도 더 깊은 완벽한 폭포수 하락장 (Lower Low + Continuation)"
            
        print(f"■ {cat}")
        print(f"   [설명] {desc}")
        print(f"   - 발생 빈도: {count}건 ({ratio:.1f}%)")
        print(f"   - 승률(> 0%): {win_rate:.1f}%")
        print(f"   - 평균 5일 수익률: {avg_ret:.2f}%\n")

if __name__ == "__main__":
    main()
