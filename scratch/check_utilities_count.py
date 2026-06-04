import os
import psycopg2

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD')
    )

conn = get_connection()
cur = conn.cursor()

# 1. Total stocks in Multi-Utilities on latest date
query_raw = """
SELECT ib.stock_code, ib.wics_name
FROM visual.vsl_anly_stocks_price_subindex01 ib
WHERE ib.date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
  AND ib.wics_name = '복합유틸리티'
"""
cur.execute(query_raw)
raw_stocks = cur.fetchall()
print(f"Raw stocks in 복합유틸리티 on latest date: {len(raw_stocks)}")
for s in raw_stocks:
    print(s)

# 2. Check ROE for these stocks
for s_code, _ in raw_stocks:
    cur.execute(f"SELECT stock_name, roe FROM (SELECT shortcode as stock_code, stock_name, roe FROM company.kis_kospi_info UNION ALL SELECT shortcode as stock_code, stock_name, roe FROM company.kis_kosdaq_info) t WHERE stock_code = '{s_code}'")
    res = cur.fetchone()
    print(f"Stock {s_code}: {res}")

conn.close()
