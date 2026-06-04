import os
import pandas as pd
import psycopg2

def load_env(filepath):
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('.env')
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

q1 = """
WITH histo_base AS (
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
)
SELECT 
    date, stock_name, histogram, lag_histogram,
    CASE 
        WHEN histogram < 0 AND histogram > lag_histogram THEN 1 
        WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 
        WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 
        WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 
        ELSE 4
    END as phase
FROM histo_base
WHERE stock_name = '한화오션' AND date BETWEEN '2026-03-25' AND '2026-04-05'
ORDER BY date;
"""
print("--- 한화오션 국면 ---")
print(pd.read_sql_query(q1, conn))

# 2. Check Theme and Trade Value Rank for 2026-03-31
q2 = """
WITH histo_base AS (
    SELECT m.date, m.stock_code, m.stock_name, (m.macd - m.signal) AS histogram, LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram FROM visual.vsl_anly_stocks_price_subindex02 m
),
phase_classification AS (
    SELECT date, stock_code, stock_name, CASE WHEN histogram < 0 AND histogram > lag_histogram THEN 1 WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 ELSE 4 END as phase
    FROM histo_base
    WHERE date = '2026-03-31'
),
theme_aggregation AS (
    SELECT nt.theme_name, p.date, COUNT(*) as total_cnt, SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt, SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt, SUM(v1.trade_value) / COUNT(*) AS avg_trade_value
    FROM industry.theme_name_list nt 
    JOIN phase_classification p ON nt.stock_code = p.stock_code
    LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    GROUP BY nt.theme_name, p.date
    HAVING COUNT(*) >= 5 
),
final_ratio AS (
    SELECT *, ROUND(((phase1_cnt::numeric * 1.5 + phase3_cnt::numeric) / total_cnt), 4) as weighted_score, ROW_NUMBER() OVER(PARTITION BY date ORDER BY avg_trade_value DESC) as trade_value_rank
    FROM theme_aggregation
)
SELECT * FROM final_ratio WHERE theme_name = '해양플랜트' OR theme_name = '조선';
"""
print("--- 테마 정보 ---")
print(pd.read_sql_query(q2, conn))
