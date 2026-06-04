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
    nt.theme_name
    , COUNT(*) as count
FROM company.krx_stocks_fundamental_info fb
LEFT JOIN company.naver_theme nt ON fb.code = nt.stock_code
WHERE fb.date = (SELECT MAX(date) FROM company.krx_stocks_fundamental_info)
  AND fb.pbr = 0
GROUP BY nt.theme_name
ORDER BY count DESC;
"""

try:
    conn = get_connection()
    df = pd.read_sql(query, conn)
    print("\n[ PBR이 0인 종목들의 테마별 분포 ]")
    print(df)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
