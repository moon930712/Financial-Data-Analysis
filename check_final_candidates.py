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
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

try:
    with open('src/sql/stock_sector_phase_master.sql', 'r', encoding='utf-8') as f:
        query = f.read()
    
    # 랭킹 logic is partitioned by sector. I'll just remove the sector filter and look at all stocks.
    query = query.replace("AND ( 'All' IN (${wics_name:sqlstring}) OR sector_name IN (${wics_name:sqlstring}) )", "")
    
    df = pd.read_sql_query(query, conn)
    target_stocks = ['대한전선', '일진전기', '한화손해보험', '롯데손해보험', '한글과컴퓨터', '하나금융지주', '현대차']
    
    print("\n[ Target Stocks Status ]")
    res = df[df['종목명'].isin(target_stocks)]
    # Filter columns to be safe
    cols = ['날짜', '업종명', '종목명', '현재국면', '업종내시총순위']
    print(res[cols].to_string(index=False))

    # Also find top Phase 1 stocks overall
    print("\n[ Global Top 10 Recovery Stocks (by dist from 0) ]")
    print(df[df['현재국면'].str.contains('회복')].head(10)[cols].to_string(index=False))

finally:
    conn.close()
