import os
import psycopg2
import pandas as pd
from datetime import datetime, timedelta

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

def get_stock_level_backtest(start_date, end_date):
    conn = get_connection()
    
    # 1. 선정 업종 (Top 3 for brevity, or Top 5 as requested by logic)
    # We use the efficiency logic: Efficiency = ROE / PBR
    query_sectors = f"""
    WITH sector_data AS (
        SELECT ib.wics_name, fb.date, AVG(fb.pbr) as avg_pbr, 
               (SELECT AVG(r.roe) FROM company.financial_factor_quarterly r WHERE r.stock_code = fb.code AND r.est_dt <= '{start_date}') as avg_roe
        FROM company.krx_stocks_fundamental_info fb
        JOIN visual.vsl_anly_stocks_price_subindex01 ib ON fb.code = ib.stock_code
        WHERE fb.date = '{start_date}'
        GROUP BY ib.wics_name, fb.date
    )
    SELECT wics_name, avg_roe, avg_pbr, (avg_roe / NULLIF(avg_pbr, 0)) as efficiency
    FROM sector_data
    WHERE avg_roe > 0 AND avg_pbr > 0
    ORDER BY efficiency DESC
    LIMIT 5
    """
    top_sectors_df = pd.read_sql_query(query_sectors, conn)
    top_sectors = top_sectors_df['wics_name'].tolist()
    
    # 2. 업종별 종목 상세 데이터
    results = []
    for sector in top_sectors:
        query_stocks = f"""
        WITH sector_stocks AS (
            SELECT DISTINCT stock_code
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE wics_name = '{sector}' AND date = '{start_date}'
        ),
        latest_roe AS (
            SELECT stock_code, roe
            FROM (
                SELECT stock_code, roe, ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY est_dt DESC) as rn
                FROM company.financial_factor_quarterly
                WHERE est_dt <= '{start_date}' AND roe IS NOT NULL
            ) t WHERE rn = 1
        ),
        pbr_val AS (
            SELECT code as stock_code, pbr
            FROM company.krx_stocks_fundamental_info
            WHERE date = '{start_date}'
        ),
        price_start AS (
            SELECT stock_code, close as start_price
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE date = '{start_date}'
        ),
        price_end AS (
            SELECT stock_code, close as end_price
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE date = '{end_date}'
        )
        SELECT 
            '{sector}' as sector_name,
            s.stock_code,
            r.roe,
            p.pbr,
            ps.start_price,
            pe.end_price
        FROM sector_stocks s
        JOIN latest_roe r ON s.stock_code = r.stock_code
        JOIN pbr_val p ON s.stock_code = p.stock_code
        JOIN price_start ps ON s.stock_code = ps.stock_code
        LEFT JOIN price_end pe ON s.stock_code = pe.stock_code
        """
        df_stocks = pd.read_sql_query(query_stocks, conn)
        results.append(df_stocks)
        
    conn.close()
    return pd.concat(results) if results else pd.DataFrame()

if __name__ == "__main__":
    print("--- 2024 Stock Level Data ---")
    df_24 = get_stock_level_backtest('2024-01-02', '2025-01-02')
    # Filter for top N stocks per sector to keep output readable
    df_24_summary = df_24.groupby('sector_name').head(2) 
    print(df_24_summary)
    df_24.to_csv(r'c:\Users\Hubnet\antigravity\results\stock_backtest_2024_full.csv', index=False)
    
    print("\n--- 2025 Stock Level Data ---")
    df_25 = get_stock_level_backtest('2025-01-02', '2025-06-30') # current approximate
    df_25_summary = df_25.groupby('sector_name').head(2)
    print(df_25_summary)
    df_25.to_csv(r'c:\Users\Hubnet\antigravity\results\stock_backtest_2025_full.csv', index=False)
