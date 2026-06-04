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

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

# Check columns in KIS tables
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='kis_kospi_info'")
print('KOSPI cols:', [r[0] for r in cur.fetchall()])

# Test joining by name
query_by_name = """
SELECT ib.stock_name, ib.stock_code, ki.shortcode, ki.roe 
FROM visual.vsl_anly_stocks_price_subindex01 ib
JOIN company.kis_kospi_info ki ON ib.stock_name = ki.koreanname
WHERE ib.date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
LIMIT 5
"""
try:
    cur.execute(query_by_name)
    print("\nJoined by Name:")
    for row in cur.fetchall():
        print(row)
except psycopg2.Error as e:
    print("\nError joining by name:", e)

# Also check difference in coverage
query_coverage = """
WITH latest_ib AS (
    SELECT stock_code, stock_name FROM visual.vsl_anly_stocks_price_subindex01 
    WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
),
all_kis AS (
    SELECT shortcode, koreanname, roe FROM company.kis_kospi_info
    UNION ALL
    SELECT shortcode, koreanname, roe FROM company.kis_kosdaq_info
)
SELECT 
    (SELECT COUNT(*) FROM latest_ib i JOIN all_kis k ON i.stock_code = (CASE WHEN k.shortcode LIKE 'F%' THEN SUBSTRING(k.shortcode, 2) ELSE k.shortcode END)) as count_by_code,
    (SELECT COUNT(*) FROM latest_ib i JOIN all_kis k ON i.stock_name = k.koreanname) as count_by_name
"""
try:
    conn.rollback()
    cur.execute(query_coverage)
    counts = cur.fetchone()
    print(f"\nCoverage Comparison:")
    print(f"By Code (F% parsing): {counts[0]}")
    print(f"By Name (koreanname): {counts[1]}")
except psycopg2.Error as e:
    print("\nError on coverage logic:", e)

conn.close()
