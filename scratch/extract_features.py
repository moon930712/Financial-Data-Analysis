import psycopg2
import pandas as pd
import numpy as np
import warnings
import os
warnings.filterwarnings('ignore')

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

query_grades = """
WITH all_valid_dates AS (SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2023-10-01')
, theme_histo_base AS (
    SELECT m.date, m.stock_code, (m.macd - m.signal) AS histogram, LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m WHERE m.date IN (SELECT date FROM all_valid_dates)
)
, theme_phase_classification AS (
    SELECT date, stock_code, CASE WHEN histogram < 0 AND histogram > lag_histogram THEN 1 WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 ELSE 4 END as phase
    FROM theme_histo_base
)
, theme_aggregation AS (
    SELECT nt.theme_name, p.date, COUNT(*) as total_cnt, SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt, SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt, SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt, SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
    FROM industry.theme_name_list nt INNER JOIN theme_phase_classification p ON nt.stock_code = p.stock_code LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    WHERE v1.close > 1000 GROUP BY nt.theme_name, p.date HAVING COUNT(*) >= 5
)
, final_ranking AS (
    SELECT date, theme_name, total_cnt, ROW_NUMBER() OVER(PARTITION BY date ORDER BY ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, total_cnt DESC) AS global_rank
    FROM theme_aggregation
)
SELECT date, theme_name, CASE WHEN global_rank <= 25 THEN '1등급' WHEN global_rank <= 50 THEN '2등급' WHEN global_rank <= 75 THEN '3등급' WHEN global_rank <= 100 THEN '4등급' WHEN global_rank <= 125 THEN '5등급' ELSE '6등급' END AS grade
FROM final_ranking ORDER BY theme_name, date
"""
print("1. Extracting Theme Grades...")
df_grades = pd.read_sql(query_grades, conn)
df_grades['date'] = pd.to_datetime(df_grades['date'])

query_indicators = """
WITH valid_dates AS (SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2023-10-01')
, smart_money AS (
    SELECT date, stock_code, SUM(CASE WHEN investor IN ('기관합계', '외국인') THEN net_trade_vol ELSE 0 END) as sm_flow
    FROM visual.vsl_krx_stocks_investor_shares_trading_info
    WHERE date IN (SELECT date FROM valid_dates)
    GROUP BY date, stock_code
)
, stock_indicators AS (
    SELECT 
        v1.date, v1.stock_code, nt.theme_name,
        v2.rsi, v1.trade_value,
        (v1.close / NULLIF(v1.ma20, 0)) * 100 AS disparity_20,
        (v2.macd - v2.signal) AS macd_hist,
        COALESCE(sm.sm_flow, 0) as sm_flow
    FROM visual.vsl_anly_stocks_price_subindex01 v1
    JOIN visual.vsl_anly_stocks_price_subindex02 v2 ON v1.stock_code = v2.stock_code AND v1.date = v2.date
    JOIN industry.theme_name_list nt ON v1.stock_code = nt.stock_code
    LEFT JOIN smart_money sm ON v1.stock_code = sm.stock_code AND v1.date = sm.date
    WHERE v1.date >= '2023-10-01' AND v1.close > 1000
)
SELECT 
    date, theme_name,
    AVG(rsi) as avg_rsi,
    SUM(trade_value) as total_trade_value,
    AVG(disparity_20) as avg_disparity_20,
    SUM(sm_flow) as total_sm_flow,
    AVG(macd_hist) as avg_macd_hist
FROM stock_indicators
GROUP BY date, theme_name
"""
print("2. Extracting Theme Indicators...")
df_indicators = pd.read_sql(query_indicators, conn)
df_indicators['date'] = pd.to_datetime(df_indicators['date'])
conn.close()

print("3. Merging and Processing Features...")
# Merge grades and indicators
df = pd.merge(df_grades, df_indicators, on=['theme_name', 'date'], how='inner')

# Sort by theme and date
df = df.sort_values(['theme_name', 'date']).reset_index(drop=True)

# Calculate volume spike (current day total_trade_value / 20-day moving average of total_trade_value)
df['vol_ma20'] = df.groupby('theme_name')['total_trade_value'].transform(lambda x: x.rolling(window=20, min_periods=1).mean().shift(1))
df['volume_spike'] = df['total_trade_value'] / df['vol_ma20']

# MACD trend (is histogram increasing?)
df['prev_macd_hist'] = df.groupby('theme_name')['avg_macd_hist'].shift(1)
df['macd_improving'] = (df['avg_macd_hist'] > df['prev_macd_hist']).astype(int)

# Target Variable: Next day's grade
df['next_grade'] = df.groupby('theme_name')['grade'].shift(-1)

# Filter: We only care about days when the theme is currently at '6등급'
df_6 = df[df['grade'] == '6등급'].copy()

# Drop rows where next_grade is NaN (last day of data)
df_6 = df_6.dropna(subset=['next_grade'])

# Create binary target: 1 if Success (jumps to 1 or 2), 0 if Fail (stays at 6)
# Note: we can ignore jumps to 3, 4, 5 for now to make it a clean binary problem, or mark them as 0
def categorize_target(grade):
    if grade in ['1등급', '2등급']:
        return 1
    elif grade == '6등급':
        return 0
    else:
        return -1 # Other jumps

df_6['target'] = df_6['next_grade'].apply(categorize_target)

# Filter out the intermediate jumps to focus purely on Success vs Fail
df_clean = df_6[df_6['target'] != -1]

print(f"Dataset ready. Total 6등급 days: {len(df_6)}")
print(f"Target 1 (Jumped to 1/2): {len(df_clean[df_clean['target'] == 1])}")
print(f"Target 0 (Stayed at 6): {len(df_clean[df_clean['target'] == 0])}")

out_path = os.path.abspath('scratch/theme_6_features.csv')
df_clean.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"Data saved to {out_path}")
