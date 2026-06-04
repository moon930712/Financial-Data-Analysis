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

query = """
SELECT ib.stock_code, ci.stock_name, ci.roe
FROM visual.vsl_anly_stocks_price_subindex01 ib
LEFT JOIN (
    SELECT stock_code, stock_name, roe FROM company.kis_kospi_info
    UNION ALL
    SELECT stock_code, stock_name, roe FROM company.kis_kosdaq_info
) ci ON ib.stock_code = ci.stock_code
WHERE ib.date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
  AND ib.wics_name = '복합유틸리티'
"""
cur.execute(query)
print("Stocks in 복합유틸리티:")
for row in cur.fetchall():
    print(row)

cur.execute("SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01")
print(f"Latest Date: {cur.fetchone()[0]}")

conn.close()
