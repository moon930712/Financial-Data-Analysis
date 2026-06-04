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

def gather_viz_data():
    conn = get_connection()
    
    # 1. 시점 정보
    current_date = pd.read_sql_query("SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01", conn).iloc[0,0]
    start_date = '2024-01-02'
    
    # 2. 업종별 현재 PBR 및 ROE (중앙값)
    # ROE는 financial_factor_quarterly의 최신 데이터
    query_fund = """
    WITH current_stocks AS (
        SELECT DISTINCT stock_code, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = %s
    ),
    latest_roe AS (
        SELECT stock_code, roe
        FROM (
            SELECT stock_code, roe, ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY est_dt DESC) as rn
            FROM company.financial_factor_quarterly
            WHERE est_dt <= %s AND roe IS NOT NULL
        ) t WHERE rn = 1
    ),
    curr_pbr AS (
        SELECT code as stock_code, pbr
        FROM company.krx_stocks_fundamental_info
        WHERE date = %s
    )
    SELECT 
        s.wics_name,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.pbr) as median_pbr,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.roe) as median_roe
    FROM current_stocks s
    JOIN curr_pbr p ON s.stock_code = p.stock_code
    LEFT JOIN latest_roe r ON s.stock_code = r.stock_code
    GROUP BY s.wics_name
    """
    df_fund = pd.read_sql_query(query_fund, conn, params=(current_date, current_date, current_date))
    
    # 3. 업종별 가격 수익률 (2024-01-02 대비 현재)
    query_price = """
    WITH start_p AS (
        SELECT wics_name, AVG(close) as avg_start_price
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = %s
        GROUP BY wics_name
    ),
    end_p AS (
        SELECT wics_name, AVG(close) as avg_end_price
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = %s
        GROUP BY wics_name
    )
    SELECT s.wics_name, 
           (e.avg_end_price / s.avg_start_price - 1) * 100 as price_return_pct
    FROM start_p s
    JOIN end_p e ON s.wics_name = e.wics_name
    """
    df_price = pd.read_sql_query(query_price, conn, params=(start_date, current_date))
    
    conn.close()
    
    # 데이터 병합
    df_viz = pd.merge(df_fund, df_price, on='wics_name')
    df_viz.to_csv(r'c:\Users\Hubnet\antigravity\results\pbr_price_roe_viz_data.csv', index=False, encoding='utf-8-sig')
    print("Visualization data gathered.")
    print(df_viz.head())

if __name__ == "__main__":
    gather_viz_data()
