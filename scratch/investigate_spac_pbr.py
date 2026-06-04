import psycopg2, os
import pandas as pd

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
    return psycopg2.connect(host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432), dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'))

query = """
SELECT 
    nt.stock_name
    , nt.stock_code
    , rb.roe
    , fb.pbr
    , fb.date
FROM company.naver_theme nt
JOIN (
    SELECT koreanname, roe FROM company.kis_kospi_info
    UNION ALL
    SELECT koreanname, roe FROM company.kis_kosdaq_info
) rb ON nt.stock_name = rb.koreanname
LEFT JOIN company.krx_stocks_fundamental_info fb ON nt.stock_code = fb.code
WHERE nt.theme_name = '기업인수목적회사(SPAC)'
  AND (fb.date = (SELECT MAX(date) FROM company.krx_stocks_fundamental_info) OR fb.date IS NULL)
"""

try:
    conn = get_connection()
    df = pd.read_sql(query, conn)
    print("\n[ SPAC 테마 종목별 데이터 확인 ]")
    print(df)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
