import os
import psycopg2
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def load_env(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('../.env')
load_env('.env')

print("1. 데이터베이스에서 종목별 최신 및 3년 역사적 데이터를 로드합니다 (visual 업종 매핑)...")

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
            AVG(NULLIF(pbr, 0)) as avg_pbr_3yr
        FROM company.krx_stocks_fundamental_info
        WHERE date >= (SELECT max_d FROM latest_date) - INTERVAL '3 years'
        GROUP BY code
    ),
    current_stats AS (
        SELECT 
            code, per, pbr
        FROM company.krx_stocks_fundamental_info
        WHERE date = (SELECT max_d FROM latest_date)
    ),
    visual_info AS (
        SELECT DISTINCT stock_code, stock_name, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
    ),
    company_info AS (
        SELECT shortcode AS stock_code, koreanname AS stock_name, roe, 'KOSPI' AS market_type
        FROM company.kis_kospi_info
        UNION ALL
        SELECT shortcode AS stock_code, koreanname AS stock_name, roe, 'KOSDAQ' AS market_type
        FROM company.kis_kosdaq_info
    ),
    market_info AS (
        SELECT v.stock_code, v.stock_name, v.wics_name, ci.roe, ci.market_type
        FROM visual_info v
        JOIN company_info ci ON v.stock_code = ci.stock_code
    )
    SELECT 
        m.stock_code,
        m.stock_name,
        COALESCE(m.wics_name, '기타') as industry,
        m.market_type,
        m.roe,
        c.per as current_per,
        c.pbr as current_pbr,
        h.avg_pbr_3yr
    FROM market_info m
    JOIN current_stats c ON m.stock_code = c.code
    JOIN historical_stats h ON m.stock_code = h.code
    WHERE m.wics_name IS NOT NULL
    """
    
    df = pd.read_sql_query(query, conn)
    
    # 기초 연산 - ROE는 DB에서 가져온 값을 사용, 결측치 및 형변환 처리
    df['roe'] = pd.to_numeric(df['roe'], errors='coerce').fillna(-5.0)
    
    df['pbr_discount_ratio'] = df['current_pbr'] / df['avg_pbr_3yr']
    df['is_undervalued'] = ((df['current_pbr'] <= df['avg_pbr_3yr'] * 0.9) & (df['current_pbr'] < 1.5)).astype(int)

    print("2. 업종별 팩터(Factor) 계산 및 Z-Score 표준화를 진행합니다...")
    
    # 업종 단위 집계 (KOSPI/KOSDAQ 구분 롤백)
    industry_df = df.groupby('industry').agg(
        stock_count=('stock_code', 'count'),
        avg_roe=('roe', 'mean'),                                
        avg_pbr_discount=('pbr_discount_ratio', 'mean'),        
        undervalued_count=('is_undervalued', 'sum')
    ).reset_index()
    
    industry_df['undervalue_density'] = (industry_df['undervalued_count'] / industry_df['stock_count']) * 100
    industry_df = industry_df[industry_df['stock_count'] >= 5].copy()

    def calc_zscore(series, invert=False):
        z = (series - series.mean()) / series.std()
        if invert:
            return -z 
        return z

    industry_df['z_fundamental'] = calc_zscore(industry_df['avg_roe'])
    industry_df['z_value'] = calc_zscore(industry_df['avg_pbr_discount'], invert=True)  
    industry_df['z_density'] = calc_zscore(industry_df['undervalue_density'])
    industry_df['z_volume_surge'] = 0.0 
    
    industry_df['total_z_score'] = (
        (industry_df['z_density'] * 0.4) + 
        (industry_df['z_value'] * 0.3) + 
        (industry_df['z_fundamental'] * 0.3)
    )
    
    final_ranking = industry_df.sort_values(by='total_z_score', ascending=False).reset_index(drop=True)
    final_ranking.index = final_ranking.index + 1
    final_ranking.insert(0, 'rank', final_ranking.index)
    
    print("\n최종 업종 랭킹 (Total Z-Score 기준 상위 10개 업종):")
    display_cols = ['rank', 'industry', 'total_z_score', 'z_density', 'z_value', 'z_fundamental', 'stock_count', 'undervalue_density']
    pd.set_option('display.float_format', '{:.2f}'.format)
    print(final_ranking[display_cols].head(10))

    # 실행 경로에 따른 동적 저장 처리
    out_dir = '../results' if not os.path.exists('results') else 'results'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    final_ranking.to_csv(f'{out_dir}/industry_zscore_ranking.csv', index=False, encoding='utf-8-sig')
    print(f"\n[성공] 업종별 Z-Score 랭킹 결과가 '{out_dir}/industry_zscore_ranking.csv' 로 저장되었습니다.")

except Exception as e:
    print(f"Error executing strategy: {e}")
finally:
    if 'conn' in locals():
        conn.close()
