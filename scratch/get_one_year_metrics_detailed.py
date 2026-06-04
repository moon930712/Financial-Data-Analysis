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

def get_one_year_metrics_detailed(start_date, end_date):
    conn = get_connection()
    
    # 1. 선정 업종 5개 추출 (Efficiency로 랭킹)
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
    
    query_names = "SELECT DISTINCT stock_code, stock_name FROM company.kis_closing_price_sale2"
    df_names = pd.read_sql_query(query_names, conn)

    all_results = []
    for sector in top_sectors:
        query_one_year = f"""
        WITH 
        purchase_data AS (
            SELECT fb.code as stock_code, fb.pbr as buy_pbr, ib.close as buy_price,
            (SELECT roe FROM company.financial_factor_quarterly r WHERE r.stock_code = fb.code AND r.est_dt <= '{start_date}' ORDER BY r.est_dt DESC LIMIT 1) as buy_roe
            FROM company.krx_stocks_fundamental_info fb
            JOIN visual.vsl_anly_stocks_price_subindex01 ib ON fb.code = ib.stock_code AND fb.date = ib.date
            WHERE fb.date = '{start_date}' AND ib.wics_name = '{sector}'
        ),
        end_data AS (
            SELECT f.code as stock_code, f.pbr as end_pbr, ib.close as end_price,
            (SELECT roe FROM company.financial_factor_quarterly r WHERE r.stock_code = f.code AND r.est_dt <= '{end_date}' ORDER BY r.est_dt DESC LIMIT 1) as end_roe
            FROM company.krx_stocks_fundamental_info f
            JOIN visual.vsl_anly_stocks_price_subindex01 ib ON f.code = ib.stock_code AND f.date = ib.date
            WHERE f.date = '{end_date}'
        )
        SELECT 
            '{sector}' as sector_name,
            pd.stock_code,
            pd.buy_roe, pd.buy_pbr, pd.buy_price,
            ed.end_roe, ed.end_pbr, ed.end_price
        FROM purchase_data pd
        JOIN end_data ed ON pd.stock_code = ed.stock_code
        ORDER BY pd.buy_roe / NULLIF(pd.buy_pbr, 0) DESC
        LIMIT 2
        """
        df_one_year = pd.read_sql_query(query_one_year, conn)
        df_one_year = pd.merge(df_one_year, df_names, on='stock_code', how='left')
        all_results.append(df_one_year)
        
    conn.close()
    return pd.concat(all_results) if all_results else pd.DataFrame()

if __name__ == "__main__":
    print("Gathering 1-Year Detailed Metrics...")
    df_24 = get_one_year_metrics_detailed('2024-01-02', '2025-01-02')
    df_24.to_csv(r'c:\Users\Hubnet\antigravity\results\one_year_metrics_2024.csv', index=False, encoding='utf-8-sig')
    
    df_25 = get_one_year_metrics_detailed('2025-01-02', '2026-04-14') # current
    df_25.to_csv(r'c:\Users\Hubnet\antigravity\results\one_year_metrics_2025.csv', index=False, encoding='utf-8-sig')
    print("Done.")
