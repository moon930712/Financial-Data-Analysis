import os
import psycopg2
import pandas as pd
import traceback
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

print("Connecting to DB and loading universe with industry data...")
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
    ),
    base_data AS (
        SELECT 
            m.stock_code,
            m.stock_name,
            m.corp_cls,
            COALESCE(m.wics_name1, '기타') as industry,
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
    )
    SELECT 
        *,
        AVG(current_pbr) OVER(PARTITION BY industry) as industry_avg_pbr,
        AVG(current_per) OVER(PARTITION BY industry) as industry_avg_per
    FROM base_data
    """
    
    df = pd.read_sql_query(query, conn)
    
    # 1. 흑자 가치주 스크리닝 (동종업계 대비 저평가 + 본인 3년 평균 대비 저평가)
    profitable_value_stocks = df[
        (df['current_per'] > 0) & (df['current_per'] <= 10) & 
        (df['current_pbr'] > 0) & (df['current_pbr'] <= 1.0) &
        (df['current_pbr'] <= df['avg_pbr_3yr'] * 0.9) &
        (df['current_pbr'] <= df['industry_avg_pbr'] * 0.8) # 업종 평균보다 20% 이상 저평가
    ].sort_values(by=['industry', 'current_pbr'])

    # 2. 적자 또는 미래성장 가치주 스크리닝 (동종업계 대비 저평가 + 본인 3년 밴드 최하단)
    deficit_value_stocks = df[
        (df['current_per'].isnull() | (df['current_per'] <= 0)) & 
        (df['current_pbr'] > 0) & 
        (df['current_pbr'] <= df['avg_pbr_3yr'] * 0.75) &
        (df['current_pbr'] <= df['min_pbr_3yr'] * 1.2) &
        (df['current_pbr'] <= df['industry_avg_pbr'] * 0.8) # 업종 평균보다 20% 이상 저평가
    ].sort_values(by=['industry', 'current_pbr'])

    print(f"Total Universe Stocks with Industry & 3-Year Data: {len(df)}")
    
    print(f"\n=== [업종대비+과거대비 저평가] 흑자 가치주: {len(profitable_value_stocks)} 종목 ===")
    print(profitable_value_stocks[['stock_name', 'industry', 'current_pbr', 'industry_avg_pbr', 'avg_pbr_3yr']].head(10))
    
    print(f"\n=== [업종대비+과거대비 저평가] 적자/성장 가치주: {len(deficit_value_stocks)} 종목 ===")
    print(deficit_value_stocks[['stock_name', 'industry', 'current_pbr', 'industry_avg_pbr', 'avg_pbr_3yr']].head(10))

    profitable_value_stocks.to_csv('profitable_industry_screener.csv', index=False, encoding='utf-8-sig')
    deficit_value_stocks.to_csv('deficit_industry_screener.csv', index=False, encoding='utf-8-sig')
    print("\nResults exported to new CSV files (profitable_industry_screener.csv, deficit_industry_screener.csv) successfully.")

except Exception as e:
    print(f"\nError executing strategy: {e}")
    traceback.print_exc()
finally:
    if 'conn' in locals():
        conn.close()
