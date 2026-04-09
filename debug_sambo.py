import os
import psycopg2
import pandas as pd

def load_env():
    with open('c:/Users/Hubnet/antigravity/.env', 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env()
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
        s.stock_code, s.stock_name, s.wics_name, f.pbr, k.roe, a.has_sell_opinion
    FROM visual.vsl_anly_stocks_price_subindex01 s
    LEFT JOIN company.krx_stocks_fundamental_info f ON s.stock_code = f.code AND s.date = f.date
    LEFT JOIN (
        SELECT shortcode AS stock_code, roe FROM company.kis_kosdaq_info
        UNION ALL
        SELECT shortcode AS stock_code, roe FROM company.kis_kospi_info
    ) k ON s.stock_code = k.stock_code
    LEFT JOIN (
        SELECT code AS stock_code,
            MAX(CASE WHEN inv_opi IN ('매도', 'Sell') THEN 1 ELSE 2 END) AS has_sell_opinion
        FROM llm.naver_stock_report
        GROUP BY code
    ) a ON s.stock_code = a.stock_code
    WHERE s.stock_name LIKE '%삼보판지%'
    ORDER BY s.date DESC LIMIT 1;
    """
    df = pd.read_sql_query(query, conn)
    print("--- 삼보판지 데이터 확인 ---")
    print(df)
finally:
    conn.close()
