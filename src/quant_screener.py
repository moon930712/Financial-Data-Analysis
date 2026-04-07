import os
import psycopg2
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

def load_env(filepath):
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('.env')

print("Connecting to DB and loading universe...")
try:
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

    query = """
    WITH latest_date AS (
        SELECT MAX(date) as max_d FROM company.krx_stocks_fundamental_info
    ),
    historical_stats AS (
        SELECT 
            code,
            AVG(NULLIF(per, 0)) as avg_per_3yr,
            AVG(NULLIF(pbr, 0)) as avg_pbr_3yr,
            MIN(NULLIF(pbr, 0)) as min_pbr_3yr
        FROM company.krx_stocks_fundamental_info
        WHERE date >= (SELECT max_d FROM latest_date) - INTERVAL '3 years'
        GROUP BY code
    ),
    current_stats AS (
        SELECT 
            code, per, pbr, eps, bps, div
        FROM company.krx_stocks_fundamental_info
        WHERE date = (SELECT max_d FROM latest_date)
    )
    SELECT 
        m.stock_code,
        m.stock_name,
        m.corp_cls,
        c.per as current_per,
        c.pbr as current_pbr,
        c.bps as current_bps,
        c.div as current_div,
        h.avg_per_3yr,
        h.avg_pbr_3yr,
        h.min_pbr_3yr
    FROM company.master_company_list m
    JOIN current_stats c ON m.stock_code = c.code
    JOIN historical_stats h ON m.stock_code = h.code
    """
    
    df = pd.read_sql_query(query, conn)
    
    # 1. 흑자 가치주 스크리닝: 현재 PER <= 10, 현재 PBR <= 1.0, 
    # 또한 현재 PBR이 과거 3년 평균 PBR보다 10% 이상 저렴한 상태
    profitable_value_stocks = df[
        (df['current_per'] > 0) & (df['current_per'] <= 10) & 
        (df['current_pbr'] > 0) & (df['current_pbr'] <= 1.0) &
        (df['current_pbr'] <= df['avg_pbr_3yr'] * 0.9)
    ].sort_values(by='current_pbr')

    # 2. 적자 또는 미래성장 가치주 스크리닝:
    # PER은 의미 없으므로 제외. 자산대비 주가인 PBR만 판단.
    # 현재 PBR이 본인의 과거 3년 평균보다 25% 이상 낮으면서(큰 하락), 3년 최저치에 근접한 수준(min_pbr의 1.2배 이내)
    deficit_value_stocks = df[
        (df['current_per'].isnull() | (df['current_per'] <= 0)) & 
        (df['current_pbr'] > 0) & 
        (df['current_pbr'] <= df['avg_pbr_3yr'] * 0.75) &
        (df['current_pbr'] <= df['min_pbr_3yr'] * 1.2)
    ].sort_values(by='current_pbr')

    print(f"Total Universe Stocks with 3-Year Data: {len(df)}")
    print(f"\n=== 흑자 상태 + 역사적 평균 대비 저평가 (PER<=10, PBR<=1.0 & 3년 평균대비 10%↓): {len(profitable_value_stocks)} 종목 ===")
    print(profitable_value_stocks[['stock_name', 'current_per', 'current_pbr', 'avg_pbr_3yr']].head(10))
    
    print(f"\n=== 적자 상태 + 역사적 PBR 하단 (PER<=0, 현재PBR이 3년 평균대비 25%↓ & 역사적 최저치 근접): {len(deficit_value_stocks)} 종목 ===")
    print(deficit_value_stocks[['stock_name', 'current_pbr', 'avg_pbr_3yr', 'min_pbr_3yr']].head(10))

    profitable_value_stocks.to_csv('profitable_value_3yr_screener.csv', index=False, encoding='utf-8-sig')
    deficit_value_stocks.to_csv('deficit_value_3yr_screener.csv', index=False, encoding='utf-8-sig')
    print("\nResults exported to CSV files successfully.")

except Exception as e:
    print(f"Error executing strategy: {e}")
finally:
    if 'conn' in locals():
        conn.close()
