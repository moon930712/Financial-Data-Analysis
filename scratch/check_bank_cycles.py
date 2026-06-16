import os
import psycopg2
import pandas as pd
import numpy as np

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

env = load_env()
conn = psycopg2.connect(
    host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
    dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
)

query_stocks = """
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
SELECT 
    p.date, p.stock_code, nt.theme_name, nt.stock_name,
    p.histogram,
    CASE 
        WHEN histogram < 0 AND histogram > lag_histogram THEN 1 
        WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 
        WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 
        WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 
        ELSE 4 
    END as phase
FROM theme_histo_base p
JOIN industry.theme_name_list nt ON p.stock_code = nt.stock_code
WHERE nt.theme_name = '은행'
ORDER BY p.stock_code, p.date
"""

df_stocks = pd.read_sql(query_stocks, conn)

df_stocks['hist_mean'] = df_stocks.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
df_stocks['hist_std'] = df_stocks.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
df_stocks['z_score'] = (df_stocks['histogram'] - df_stocks['hist_mean']) / df_stocks['hist_std']

df_stocks['prev_phase'] = df_stocks.groupby('stock_code')['phase'].shift(1)
df_stocks['prev_z'] = df_stocks.groupby('stock_code')['z_score'].shift(1)
df_stocks['prev_hist'] = df_stocks.groupby('stock_code')['histogram'].shift(1)
df_stocks['prev2_hist'] = df_stocks.groupby('stock_code')['histogram'].shift(2)

df_stocks['is_neg_max'] = (
    (df_stocks['prev_phase'] == 2) & 
    (df_stocks['phase'] == 1) & 
    (df_stocks['prev_z'] <= -1.0) &
    (df_stocks['prev2_hist'] > df_stocks['prev_hist'])
)

df_stocks['is_pos_max'] = (
    (df_stocks['prev_phase'] == 3) & 
    (df_stocks['phase'] == 4) & 
    (df_stocks['prev_z'] >= 1.0) &
    (df_stocks['prev2_hist'] < df_stocks['prev_hist'])
)

extrema = df_stocks[df_stocks['is_neg_max'] | df_stocks['is_pos_max']].copy()
extrema = extrema.sort_values(['stock_code', 'date'])
extrema['type'] = np.where(extrema['is_neg_max'], -1, 1)

extrema['next_type'] = extrema.groupby('stock_code')['type'].shift(-1)
extrema['next_date'] = extrema.groupby('stock_code')['date'].shift(-1)
extrema['next_next_type'] = extrema.groupby('stock_code')['type'].shift(-2)
extrema['next_next_date'] = extrema.groupby('stock_code')['date'].shift(-2)

valid_seq = extrema[(extrema['type'] == -1) & (extrema['next_type'] == 1) & (extrema['next_next_type'] == -1)].copy()
valid_seq = valid_seq.dropna(subset=['next_next_date'])

print(f"Total Bank Cycles found: {len(valid_seq)}")

valid_seq['next_next_date'] = pd.to_datetime(valid_seq['next_next_date'])
valid_seq_2026 = valid_seq[valid_seq['next_next_date'] >= pd.to_datetime('2026-01-01')]
print(f"Bank Cycles in 2026: {len(valid_seq_2026)}")
if len(valid_seq_2026) > 0:
    print(valid_seq_2026[['stock_name', 'date', 'next_date', 'next_next_date']])
