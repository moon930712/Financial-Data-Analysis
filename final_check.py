import os
import psycopg2
import pandas as pd

def load_env(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('.env')
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'), port=5432,
    dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD')
)

try:
    with open('src/sql/stock_sector_phase_master.sql', 'r', encoding='utf-8') as f:
        query = f.read().replace("AND ( 'All' IN (${wics_name:sqlstring}) OR sector_name IN (${wics_name:sqlstring}) )", "")
    
    df = pd.read_sql_query(query, conn)
    targets = ['대한전선', '한화손해보험', '한글과컴퓨터']
    res = df[df['종목명'].isin(targets)]
    print(res[['날짜', '업종명', '종목명', '현재국면', '업종내시총순위']].to_string(index=False))

finally:
    conn.close()
