import os
import psycopg2
import pandas as pd

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
    host=env.get('DB_HOST'), port=5432,
    dbname=env.get('DB_NAME'), user=env.get('DB_USER'), password=env.get('DB_PASSWORD')
)

try:
    sql = """
    WITH histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name, (m.macd - m.signal) AS histogram,
               LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
    )
    SELECT stock_name, 
           CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN '회복기'
                WHEN histogram >= 0 AND histogram > lag_histogram THEN '상승기'
                WHEN histogram < 0 AND histogram <= lag_histogram THEN '하락기'
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN '둔화기'
           END as phase,
           histogram, lag_histogram, date
    FROM histo_base
    WHERE stock_name = 'HD현대에너지솔루션'
    ORDER BY date DESC LIMIT 1;
    """
    df = pd.read_sql_query(sql, conn)
    print(df.to_string(index=False))

finally:
    conn.close()
