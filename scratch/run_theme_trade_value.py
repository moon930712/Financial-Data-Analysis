import os
import psycopg2
import pandas as pd

def load_env(filepath):
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('.env')

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

try:
    query = """
    WITH recent_date AS (
        SELECT MAX(date) AS max_date
        FROM visual.vsl_anly_stocks_price_subindex01
    )
    SELECT 
        t.theme_name AS "테마명(섹터)",
        COUNT(t.stock_code) AS "종목수",
        SUM(p.trade_value) AS "총_거래대금",
        SUM(p.trade_value) / COUNT(t.stock_code) AS "종목당_평균_거래대금"
    FROM industry.theme_name_list t
    JOIN visual.vsl_anly_stocks_price_subindex01 p 
      ON t.stock_code = p.stock_code
    JOIN recent_date r
      ON p.date = r.max_date
    GROUP BY t.theme_name
    ORDER BY "종목당_평균_거래대금" DESC
    LIMIT 30; -- 상위 30개만 출력
    """
    df = pd.read_sql_query(query, conn)
    
    # 억 단위로 변환해서 보기 좋게 만듦 (trade_value의 단위가 원 단위인지 확인 필요하지만 통상적으로 원이거나 천원/백만원. 원이라고 가정하고 보기좋게 포맷팅)
    # pandas display settings
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df.to_markdown(index=False))
finally:
    conn.close()
