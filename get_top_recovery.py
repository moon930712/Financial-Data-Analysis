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
    WITH target_info AS (
        SELECT stock_code, stock_name, cap, wics_name2 as mid_sector, wics_name3 as sub_sector
        FROM visual.vsl_krx_stocks_cap
        WHERE date = (SELECT MAX(date) FROM visual.vsl_krx_stocks_cap)
          AND wics_name3 != '미분류'
    ),
    phase_data AS (
        SELECT m.stock_code, (m.macd - m.signal) as hist, 
               LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) as lag_hist,
               m.date
        FROM visual.vsl_anly_stocks_price_subindex02 m
    )
    SELECT ti.mid_sector, ti.sub_sector, ti.stock_name, ti.cap
    FROM target_info ti
    JOIN phase_data pd ON ti.stock_code = pd.stock_code
    WHERE pd.date = (SELECT MAX(date) FROM phase_data)
      AND pd.hist < 0 AND pd.hist > pd.lag_hist
    ORDER BY ti.cap DESC
    LIMIT 20;
    """
    df = pd.read_sql_query(sql, conn)
    print(df.to_string(index=False))

finally:
    conn.close()
