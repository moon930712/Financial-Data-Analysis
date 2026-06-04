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

def research_peak_performance_optimized():
    conn = get_connection()
    
    query = """
    WITH latest_date AS (
        SELECT MAX(date) as current_date 
        FROM visual.vsl_anly_stocks_price_subindex01
    ),
    sector_pbr_history AS (
        SELECT ib.wics_name, fb.date, fb.pbr,
               ROW_NUMBER() OVER(PARTITION BY ib.wics_name ORDER BY fb.pbr DESC) as rn
        FROM company.krx_stocks_fundamental_info fb
        JOIN visual.vsl_anly_stocks_price_subindex01 ib ON fb.code = ib.stock_code
        WHERE fb.date >= '2024-01-01'
    ),
    peak_points AS (
        SELECT wics_name, date as max_date, pbr as max_pbr
        FROM sector_pbr_history
        WHERE rn = 1
    ),
    prices_at_peak AS (
        SELECT p.wics_name, p.max_date, p.max_pbr, AVG(pr.close) as peak_price
        FROM peak_points p
        JOIN visual.vsl_anly_stocks_price_subindex01 pr ON p.wics_name = pr.wics_name AND p.max_date = pr.date
        GROUP BY p.wics_name, p.max_date, p.max_pbr
    ),
    prices_current AS (
        SELECT pr.wics_name, AVG(pr.close) as current_price
        FROM visual.vsl_anly_stocks_price_subindex01 pr
        JOIN latest_date l ON pr.date = l.current_date
        GROUP BY pr.wics_name
    )
    SELECT 
        p.wics_name as sector,
        p.max_date as peak_pbr_date,
        p.max_pbr,
        p.peak_price,
        c.current_price,
        (c.current_price / NULLIF(p.peak_price, 0) - 1) * 100 as performance_pct
    FROM prices_at_peak p
    JOIN prices_current c ON p.wics_name = c.wics_name
    ORDER BY performance_pct ASC
    """
    df = pd.read_sql_query(query, conn)
    df.to_csv(r'c:\Users\Hubnet\antigravity\results\sector_peak_performance_optimized.csv', index=False, encoding='utf-8-sig')
    print("Optimized research completed.")
    print(df.head(15))
    conn.close()

if __name__ == "__main__":
    research_peak_performance_optimized()
