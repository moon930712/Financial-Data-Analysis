import os
import psycopg2
import pandas as pd
import numpy as np
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

print("1. 데이터베이스에서 종목별 최신 및 3년 역사적 펀더멘탈 데이터를 로드합니다...")

try:
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

    # 기본 펀더멘탈 데이터 쿼리
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
    )
    SELECT 
        m.stock_code,
        m.stock_name,
        COALESCE(m.wics_name1, '기타') as industry,
        c.per as current_per,
        c.pbr as current_pbr,
        h.avg_pbr_3yr
    FROM company.master_company_list m
    JOIN current_stats c ON m.stock_code = c.code
    JOIN historical_stats h ON m.stock_code = h.code
    WHERE m.wics_name1 IS NOT NULL
    """
    
    df = pd.read_sql_query(query, conn)
    
    # 기초 연산
    # ROE 근사치 산출: PBR = PER * ROE  =>  ROE = PBR / PER
    df['roe'] = np.where((df['current_per'] > 0) & (df['current_per'].notnull()), 
                         (df['current_pbr'] / df['current_per']) * 100, 
                         -5.0) # 적자거나 PER 계산 안되면 페널티 부여
    
    # PBR 할인율 (Value): (Current PBR) / (3yr Avg PBR) 
    # 낮을 수록 저평가
    df['pbr_discount_ratio'] = df['current_pbr'] / df['avg_pbr_3yr']
    
    # 개별 종목이 저평가 조건을 만족하는지 플래그(Density용)
    df['is_undervalued'] = ((df['current_pbr'] <= df['avg_pbr_3yr'] * 0.9) & (df['current_pbr'] < 1.5)).astype(int)

    print("2. 업종(Industry)별 팩터(Factor) 계산 및 Z-Score 표준화를 진행합니다...")
    
    # 업종별 집계 수행
    industry_df = df.groupby('industry').agg(
        stock_count=('stock_code', 'count'),
        avg_roe=('roe', 'mean'),                                # Factor 1: Fundamental (수익성)
        avg_pbr_discount=('pbr_discount_ratio', 'mean'),        # Factor 2: Value (바닥론, 낮을수록 좋음)
        undervalued_count=('is_undervalued', 'sum')
    ).reset_index()
    
    # Factor 3: Quality (바닥 밀집도)
    industry_df['undervalue_density'] = (industry_df['undervalued_count'] / industry_df['stock_count']) * 100
    
    # 너무 종목 수가 적은 테마성 업종 제외 (예: 종목수 5개 미만)
    industry_df = industry_df[industry_df['stock_count'] >= 5].copy()

    # Z-Score 산출 로직
    # Z = (X - Mean) / Std
    def calc_zscore(series, invert=False):
        z = (series - series.mean()) / series.std()
        if invert:
            return -z  # 값이 낮을수록 좋은 지표(pbr_discount)는 점수를 뒤집음
        return z

    industry_df['z_fundamental'] = calc_zscore(industry_df['avg_roe'])
    industry_df['z_value'] = calc_zscore(industry_df['avg_pbr_discount'], invert=True)  # 할인율이 낮을수록 1위
    industry_df['z_density'] = calc_zscore(industry_df['undervalue_density'])
    
    # ※ 4번째 수급 모멘텀(Volume Surge) 팩터는 과거 6개월 일별 거래량 DB 테이블 연동 후 추가 예정
    industry_df['z_volume_surge'] = 0.0 # Placeholder
    
    # 최종 Total Z-Score 합산
    # 가중치: 가치보단 턴어라운드(Density) 40%, Value 30%, Fundamental 30%
    industry_df['total_z_score'] = (
        (industry_df['z_density'] * 0.4) + 
        (industry_df['z_value'] * 0.3) + 
        (industry_df['z_fundamental'] * 0.3) +
        (industry_df['z_volume_surge'] * 0.0)
    )
    
    # 랭킹 정렬
    final_ranking = industry_df.sort_values(by='total_z_score', ascending=False).reset_index(drop=True)
    final_ranking.index = final_ranking.index + 1
    
    print("\n최종 업종 랭킹 (Total Z-Score 기준 상위 10개 업종):")
    # 포맷팅하여 이쁘게 출력
    display_cols = ['industry', 'total_z_score', 'z_density', 'z_value', 'z_fundamental', 'stock_count', 'undervalue_density']
    pd.set_option('display.float_format', '{:.2f}'.format)
    print(final_ranking[display_cols].head(10))

    final_ranking.to_csv('industry_zscore_ranking.csv', index=False, encoding='utf-8-sig')
    print("\n[성공] 업종별 Z-Score 랭킹 결과가 'industry_zscore_ranking.csv' 로 저장되었습니다.")

except Exception as e:
    print(f"Error executing strategy: {e}")
finally:
    if 'conn' in locals():
        conn.close()
