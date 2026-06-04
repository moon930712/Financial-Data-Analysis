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
    query = """
    SELECT 
        COUNT(DISTINCT wics_name2) as total_mid_classes
    FROM visual.vsl_krx_stocks_cap
    WHERE wics_name2 IS NOT NULL 
      AND wics_name2 != '미분류'
      AND TRIM(wics_name2) != '';
    """
    df = pd.read_sql_query(query, conn)
    
    query_list = """
    SELECT 
        wics_name2 as wics_mid_class,
        COUNT(DISTINCT stock_code) as total_stocks
    FROM visual.vsl_krx_stocks_cap
    WHERE wics_name2 IS NOT NULL 
      AND wics_name2 != '미분류'
      AND TRIM(wics_name2) != ''
    GROUP BY wics_name2
    ORDER BY wics_name2 ASC;
    """
    df_list = pd.read_sql_query(query_list, conn)

    print(f"\n[ WICS 중분류(wics_name2) 총 개수: {df['total_mid_classes'].iloc[0]}개 ]\n")
    print(df_list.to_string(index=False))

finally:
    conn.close()
