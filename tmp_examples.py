import psycopg2
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')
import warnings
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

query_ranks = """
WITH valid_dates AS (
    SELECT DISTINCT date 
    FROM visual.vsl_anly_stocks_price_subindex01 
    WHERE date >= '2026-01-01' AND date <= '2026-05-15'
)
, histo_base AS (
    SELECT m.date, m.stock_code, m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
    WHERE m.date >= '2025-12-01' AND m.date <= '2026-05-15'
)
, phase_calc AS (
    SELECT date, stock_code, stock_name
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 2
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 3
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4
            ELSE 4
        END AS phase
    FROM histo_base
    WHERE date IN (SELECT date FROM valid_dates)
)
, theme_aggregation AS (
    SELECT nt.theme_name, p.date
        , COUNT(*) AS total_cnt
        , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) AS phase1_cnt
        , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) AS phase2_cnt
        , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) AS phase3_cnt
        , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) AS phase4_cnt
        , COALESCE(SUM(v1.trade_value), 0) / COUNT(*) AS avg_trade_value
    FROM industry.theme_name_list nt 
    INNER JOIN phase_calc p ON nt.stock_code = p.stock_code
    LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    WHERE v1.close > 1000 
    GROUP BY nt.theme_name, p.date
    HAVING COUNT(*) >= 5 
)
, trade_rank_calc AS (
    SELECT *, ROW_NUMBER() OVER(PARTITION BY date ORDER BY avg_trade_value DESC NULLS LAST) AS trade_value_rank
    FROM theme_aggregation
)
, final_ranking AS (
    SELECT date, theme_name
        , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
            ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
            ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
            total_cnt DESC
          ) AS global_rank
    FROM trade_rank_calc
    WHERE trade_value_rank <= 150
)
SELECT date, theme_name, global_rank
FROM final_ranking
ORDER BY theme_name ASC, date ASC
"""
df_ranks = pd.read_sql(query_ranks, conn)
df_ranks['date'] = pd.to_datetime(df_ranks['date']).dt.strftime('%Y-%m-%d')
df_ranks['prev_rank'] = df_ranks.groupby('theme_name')['global_rank'].shift(1)

df_ranks = df_ranks.dropna(subset=['prev_rank'])
df_ranks['prev_rank'] = df_ranks['prev_rank'].astype(int)

# Group 1: 31~60 -> 1~10
group1 = df_ranks[(df_ranks['prev_rank'] >= 31) & (df_ranks['prev_rank'] <= 60) & (df_ranks['global_rank'] <= 10)]

# Group 2: 61~100 -> 1~10
group2 = df_ranks[(df_ranks['prev_rank'] >= 61) & (df_ranks['prev_rank'] <= 100) & (df_ranks['global_rank'] <= 10)]

print("=== 황금 타점 1 (어제 31~60위 -> 오늘 1~10위) 예시 ===")
print(group1.head(5).to_string(index=False))

print("\n=== 황금 타점 2 (어제 61~100위 -> 오늘 1~10위) 예시 ===")
print(group2.head(5).to_string(index=False))

conn.close()
