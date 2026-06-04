import os
import psycopg2
import pandas as pd

def load_env(filepath):
    if not os.path.exists(filepath):
        return
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

try:
    # 1개 종목만 있는 WICS 소분류 찾기
    query = """
    SELECT 
        wics_name3 as sector_name,
        COUNT(DISTINCT stock_code) as stock_count,
        MAX(stock_name) as stock_name
    FROM visual.vsl_krx_stocks_cap
    WHERE wics_name3 IS NOT NULL 
      AND wics_name3 != '미분류'
    GROUP BY wics_name3
    HAVING COUNT(DISTINCT stock_code) = 1
    ORDER BY sector_name;
    """
    df = pd.read_sql_query(query, conn)
    
    print("\n[ 단 1개의 종목만 포함된 소분류(wics_name3) 목록 ]\n")
    if df.empty:
        print("1개 종목만 있는 소분류는 존재하지 않습니다.")
    else:
        print(df.to_string(index=False))
        
finally:
    conn.close()
