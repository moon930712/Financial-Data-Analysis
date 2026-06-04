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

def get_peak_metrics_backtest(start_date, end_date):
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
        query_peaks = f"""
        WITH 
        target_stocks AS (
            SELECT DISTINCT stock_code
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE date = '{start_date}' AND wics_name = '{sector}'
        ),
        purchase_data AS (
            SELECT fb.code as stock_code, fb.pbr as buy_pbr, ib.close as buy_price,
            (SELECT roe FROM company.financial_factor_quarterly r WHERE r.stock_code = fb.code AND r.est_dt <= '{start_date}' ORDER BY r.est_dt DESC LIMIT 1) as buy_roe
            FROM company.krx_stocks_fundamental_info fb
            JOIN visual.vsl_anly_stocks_price_subindex01 ib ON fb.code = ib.stock_code AND fb.date = ib.date
            WHERE fb.date = '{start_date}' AND ib.wics_name = '{sector}'
        ),
        peak_date_finder AS (
            SELECT stock_code, date as peak_date, close as peak_price,
            ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY close DESC, date ASC) as rn
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE date BETWEEN '{start_date}' AND '{end_date}' AND stock_code IN (SELECT stock_code FROM target_stocks)
        ),
        peak_main AS (
            SELECT * FROM peak_date_finder WHERE rn = 1
        ),
        peak_fundamentals AS (
            SELECT pm.stock_code, pm.peak_date, pm.peak_price, f.pbr as peak_pbr,
            (SELECT roe FROM company.financial_factor_quarterly r WHERE r.stock_code = pm.stock_code AND r.est_dt <= pm.peak_date ORDER BY r.est_dt DESC LIMIT 1) as peak_roe
            FROM peak_main pm
            JOIN company.krx_stocks_fundamental_info f ON pm.stock_code = f.code AND pm.peak_date = f.date
        )
        SELECT 
            '{sector}' as sector_name,
            pd.stock_code,
            pd.buy_roe, pd.buy_pbr, pd.buy_price,
            pf.peak_date, pf.peak_price, pf.peak_roe, pf.peak_pbr
        FROM purchase_data pd
        JOIN peak_fundamentals pf ON pd.stock_code = pf.stock_code
        ORDER BY pd.buy_roe / NULLIF(pd.buy_pbr, 0) DESC
        LIMIT 2
        """
        df_peaks = pd.read_sql_query(query_peaks, conn)
        df_peaks = pd.merge(df_peaks, df_names, on='stock_code', how='left')
        all_results.append(df_peaks)
        
    conn.close()
    return pd.concat(all_results) if all_results else pd.DataFrame()

if __name__ == "__main__":
    print("Gathering Detailed Peak Metrics...")
    df_peaks_24 = get_peak_metrics_backtest('2024-01-02', '2025-01-02')
    df_peaks_24.to_csv(r'c:\Users\Hubnet\antigravity\results\peak_metrics_2024.csv', index=False, encoding='utf-8-sig')
    
    df_peaks_25 = get_peak_metrics_backtest('2025-01-02', '2026-04-14')
    df_peaks_25.to_csv(r'c:\Users\Hubnet\antigravity\results\peak_metrics_2025.csv', index=False, encoding='utf-8-sig')
    print("Done.")
