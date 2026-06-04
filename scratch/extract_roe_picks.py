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
    return psycopg2.connect( host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432), dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'))

def get_top_roe_stocks():
    conn = get_connection()
    target_sectors = ['손해보험', '게임엔터테인먼트', '호텔,레스토랑,레저', '은행']
    
    query = """
    WITH industry_base AS (
        SELECT DISTINCT stock_code, stock_name, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
    ),
    fundamental_base AS (
        SELECT code AS stock_code, pbr, date
        FROM company.krx_stocks_fundamental_info
        WHERE date = (SELECT MAX(date) FROM company.krx_stocks_fundamental_info)
    ),
    roe_base AS (
        SELECT 
            CASE WHEN shortcode LIKE 'F%%' THEN SUBSTRING(shortcode, 2) ELSE shortcode END AS stock_code,
            roe
        FROM company.kis_kospi_info
        UNION ALL
        SELECT 
            shortcode AS stock_code, 
            roe
        FROM company.kis_kosdaq_info
    )
    SELECT 
        ib.wics_name,
        ib.stock_name,
        rb.roe,
        fb.pbr
    FROM industry_base ib
    JOIN roe_base rb ON ib.stock_code = rb.stock_code
    LEFT JOIN fundamental_base fb ON ib.stock_code = fb.stock_code
    WHERE ib.wics_name IN %s
    """
    df = pd.read_sql_query(query, conn, params=(tuple(target_sectors),))
    conn.close()
    
    results = []
    for sector in target_sectors:
        sector_df = df[df['wics_name'] == sector].sort_values('roe', ascending=False)
        top_stocks = sector_df.head(3)
        results.append(top_stocks)
    
    final_df = pd.concat(results)
    final_df.to_csv(r'c:\Users\Hubnet\antigravity\results\eda_top_roe_stock_picks.csv', index=False, encoding='utf-8-sig')
    print("Top ROE Stocks extracted to results/eda_top_roe_stock_picks.csv")
    print(final_df)

if __name__ == "__main__":
    get_top_roe_stocks()
