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
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def research_peak_performance_v3():
    conn = get_connection()
    
    print("Step 1: Get sector mapping...")
    # 1. Get Sector Mapping once
    mapping_query = "SELECT DISTINCT stock_code, wics_name FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2024-01-01'"
    df_map = pd.read_sql_query(mapping_query, conn)
    
    print("Step 2: Aggregate PBR by sector/date...")
    # 2. Get Sector PBR per day
    # We join and group in SQL but limit the dates
    query = """
    WITH sector_map AS (
        SELECT DISTINCT stock_code, wics_name FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2024-01-01'
    ),
    daily_sector_pbr AS (
        SELECT sm.wics_name, fb.date, AVG(fb.pbr) as avg_pbr
        FROM sector_map sm
        JOIN company.krx_stocks_fundamental_info fb ON sm.stock_code = fb.code
        WHERE fb.date >= '2024-01-01'
        GROUP BY sm.wics_name, fb.date
    ),
    sector_peak_dates AS (
        SELECT wics_name, date as max_pbr_date, avg_pbr as max_pbr,
               ROW_NUMBER() OVER(PARTITION BY wics_name ORDER BY avg_pbr DESC) as rn
        FROM daily_sector_pbr
    ),
    peak_points AS (
        SELECT wics_name, max_pbr_date, max_pbr
        FROM sector_peak_dates
        WHERE rn = 1
    ),
    daily_sector_price AS (
        SELECT wics_name, date, AVG(close) as avg_price
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '2024-01-01'
        GROUP BY wics_name, date
    ),
    latest_date AS (
        SELECT MAX(date) as current_date FROM visual.vsl_anly_stocks_price_subindex01
    )
    SELECT 
        p.wics_name as sector,
        p.max_pbr_date,
        p.max_pbr,
        pr.avg_price as peak_price,
        curr_pr.avg_price as current_price
    FROM peak_points p
    JOIN daily_sector_price pr ON p.wics_name = pr.wics_name AND p.max_pbr_date = pr.date
    JOIN latest_date l ON 1=1
    JOIN daily_sector_price curr_pr ON p.wics_name = curr_pr.wics_name AND curr_pr.date = l.current_date
    """
    df = pd.read_sql_query(query, conn)
    df['performance_pct'] = (df['current_price'] / df['peak_price'] - 1) * 100
    df = df.sort_values('performance_pct', ascending=True)
    
    df.to_csv(r'c:\Users\Hubnet\antigravity\results\sector_peak_performance_v3.csv', index=False, encoding='utf-8-sig')
    print("V3 research completed.")
    print(df.head(15))
    conn.close()

if __name__ == "__main__":
    research_peak_performance_v3()
