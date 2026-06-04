import os
import psycopg2
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
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD')
    )

def analyze_outliers():
    conn = get_connection()
    sectors = ['생물공학', '생명과학도구및서비스', '생명보험', '전기장비']
    
    query = """
    WITH sector_data AS (
        SELECT ib.wics_name, ib.date, AVG(ib.close) as avg_price, AVG(fb.pbr) as avg_pbr
        FROM visual.vsl_anly_stocks_price_subindex01 ib
        JOIN company.krx_stocks_fundamental_info fb ON ib.stock_code = fb.code AND ib.date = fb.date
        WHERE ib.date >= '2024-01-01' AND ib.wics_name IN (%s)
        GROUP BY ib.wics_name, ib.date
    ),
    endpoints AS (
        SELECT wics_name, MIN(date) as start_date, MAX(date) as end_date
        FROM sector_data
        GROUP BY wics_name
    )
    SELECT 
        e.wics_name, 
        s.avg_price as start_price, s.avg_pbr as start_pbr,
        f.avg_price as end_price, f.avg_pbr as end_pbr
    FROM endpoints e
    JOIN sector_data s ON e.wics_name = s.wics_name AND e.start_date = s.date
    JOIN sector_data f ON e.wics_name = f.wics_name AND e.end_date = f.date
    """ % (", ".join(["'%s'" % s for s in sectors]))
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Calculate Changes and BPS Growth
    df['price_chg_pct'] = (df['end_price'] / df['start_price'] - 1) * 100
    df['pbr_chg_pct'] = (df['end_pbr'] / df['start_pbr'] - 1) * 100
    
    # BPS = Price / PBR
    df['start_bps'] = df['start_price'] / df['start_pbr']
    df['end_bps'] = df['end_price'] / df['end_pbr']
    df['bps_growth_pct'] = (df['end_bps'] / df['start_bps'] - 1) * 100
    
    print("--- Detailed Outlier Analysis (2024~Present) ---")
    print(df[['wics_name', 'price_chg_pct', 'pbr_chg_pct', 'bps_growth_pct']])
    
    df.to_csv(r'c:\Users\Hubnet\antigravity\results\outlier_interpretation_data.csv', index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    analyze_outliers()
