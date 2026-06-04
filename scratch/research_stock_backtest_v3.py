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

def get_detailed_backtest(start_date, end_date):
    conn = get_connection()
    
    # 1. 선정 업종 5개 추출 (Efficiency = Avg ROE / Avg PBR)
    query_sectors = f"""
    WITH latest_roe AS (
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
    sector_map AS (
        SELECT DISTINCT stock_code, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{start_date}'
    ),
    stock_fundamental AS (
        SELECT s.wics_name, s.stock_code, r.roe, p.pbr
        FROM sector_map s
        JOIN latest_roe r ON s.stock_code = r.stock_code
        JOIN pbr_val p ON s.stock_code = p.stock_code
        WHERE r.roe > 0 AND p.pbr > 0
    )
    SELECT wics_name
    FROM stock_fundamental
    GROUP BY wics_name
    ORDER BY (AVG(roe) / NULLIF(AVG(pbr), 0)) DESC
    LIMIT 5
    """
    top_sectors_df = pd.read_sql_query(query_sectors, conn)
    top_sectors = top_sectors_df['wics_name'].tolist()
    
    # 2. 업종별 종목 상세 데이터 (명칭 포함)
    all_results = []
    
    # Stock Names source
    query_names = "SELECT stock_code, stock_name FROM company.kis_kospi_info UNION SELECT stock_code, stock_name FROM company.kis_kosdaq_info"
    df_names = pd.read_sql_query(query_names, conn)

    for sector in top_sectors:
        query_stocks = f"""
        WITH latest_roe AS (
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
            WHERE date = '{start_date}' AND wics_name = '{sector}'
        ),
        price_end AS (
            SELECT stock_code, close as end_price
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE date = '{end_date}'
        )
        SELECT 
            '{sector}' as sector_name,
            ps.stock_code,
            r.roe,
            p.pbr,
            ps.start_price,
            pe.end_price
        FROM price_start ps
        JOIN latest_roe r ON ps.stock_code = r.stock_code
        JOIN pbr_val p ON ps.stock_code = p.stock_code
        LEFT JOIN price_end pe ON ps.stock_code = pe.stock_code
        ORDER BY r.roe / NULLIF(p.pbr, 0) DESC
        LIMIT 3
        """
        df_stocks = pd.read_sql_query(query_stocks, conn)
        df_stocks = pd.merge(df_stocks, df_names, on='stock_code', how='left')
        all_results.append(df_stocks)
        
    conn.close()
    return pd.concat(all_results) if all_results else pd.DataFrame()

if __name__ == "__main__":
    print("Extracting 2024 data...")
    df_24 = get_detailed_backtest('2024-01-02', '2025-01-02')
    df_24.to_csv(r'c:\Users\Hubnet\antigravity\results\stock_backtest_2024_final.csv', index=False, encoding='utf-8-sig')
    
    print("Extracting 2025 data...")
    df_25 = get_detailed_backtest('2025-01-02', '2025-06-30')
    df_25.to_csv(r'c:\Users\Hubnet\antigravity\results\stock_backtest_2025_final.csv', index=False, encoding='utf-8-sig')
    print("Done.")
