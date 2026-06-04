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
    # 1. 통신 3사의 중분류(wics_name2), 소분류(wics_name3) 현황 
    query_telecom = """
    SELECT 
        stock_name, 
        wics_name2 as wics_mid_class, 
        wics_name3 as wics_small_class
    FROM visual.vsl_krx_stocks_cap
    WHERE stock_name IN ('SK텔레콤', 'KT', 'LG유플러스')
    GROUP BY stock_name, wics_name2, wics_name3
    ORDER BY stock_name DESC;
    """
    df_telecom = pd.read_sql_query(query_telecom, conn)
    
    print("\n[ 국내 통신 3사의 WICS 중분류(wics_name2) vs 소분류(wics_name3) 맵핑 상태 ]\n")
    print(df_telecom.to_string(index=False))

    # 2. 통신 관련 중분류(wics_name2) 하위의 모든 소분류 포함 내역 확인
    if not df_telecom.empty:
        target_wics2 = df_telecom['wics_mid_class'].iloc[0] # 통신 3사가 속한 중분류
        query_grouping = f"""
        SELECT 
            wics_name2 as wics_mid_class,
            wics_name3 as wics_small_class,
            COUNT(DISTINCT stock_code) as total_stocks
        FROM visual.vsl_krx_stocks_cap
        WHERE wics_name2 = '{target_wics2}'
        GROUP BY wics_name2, wics_name3
        ORDER BY total_stocks DESC;
        """
        df_grouping = pd.read_sql_query(query_grouping, conn)
        print(f"\n[ 중분류 '{target_wics2}' 에 속한 소분류 목록 및 종목 수 ]\n")
        print(df_grouping.to_string(index=False))

finally:
    conn.close()
