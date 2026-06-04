import os
import psycopg2
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
# scipy.stats 대신 pandas.corr 사용
from matplotlib import font_manager, rc

# 한글 폰트 설정
try:
    font_path = "C:/Windows/Fonts/malgun.ttf"
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    rc('font', family=font_name)
except:
    pass

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

def get_quarterly_data(target_date):
    """지정된 날짜 시점의 전 종목 ROE-PBR 데이터 추출"""
    conn = get_connection()
    
    # 1. PBR 데이터 (해당 일자 또는 가장 가까운 과거)
    query_pbr = f"""
    SELECT code as stock_code, pbr
    FROM company.krx_stocks_fundamental_info
    WHERE date = (SELECT MAX(date) FROM company.krx_stocks_fundamental_info WHERE date <= '{target_date}')
    """
    df_pbr = pd.read_sql_query(query_pbr, conn)
    
    # 2. ROE 데이터 (해당 일자 이전 공시된 가장 최신 분기 데이터)
    query_roe = f"""
    SELECT stock_code, roe
    FROM (
        SELECT stock_code, roe, 
               ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY est_dt DESC) as rn
        FROM company.financial_factor_quarterly
        WHERE est_dt <= '{target_date}' AND roe IS NOT NULL
    ) t WHERE rn = 1
    """
    df_roe = pd.read_sql_query(query_roe, conn)
    
    # 3. 업종 정보
    query_wics = f"""
    SELECT DISTINCT stock_code, wics_name
    FROM visual.vsl_anly_stocks_price_subindex01
    WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01 WHERE date <= '{target_date}')
    """
    df_wics = pd.read_sql_query(query_wics, conn)
    
    conn.close()
    
    # 조인
    df = pd.merge(df_wics, df_pbr, on='stock_code')
    df = pd.merge(df, df_roe, on='stock_code')
    
    # 이상치 제거 (PBR > 50, ROE < -100 or ROE > 100 등 비정상 데이터)
    df = df[(df['pbr'] > 0) & (df['pbr'] < 50)]
    df = df[(df['roe'] > -100) & (df['roe'] < 100)]
    
    return df

def analyze_correlation():
    quarter_dates = [
        '2024-03-31', '2024-06-30', '2024-09-30', '2024-12-31',
        '2025-03-31', '2025-06-30'
    ]
    
    history_corr = []
    
    for q_date in quarter_dates:
        print(f"Processing {q_date}...")
        df = get_quarterly_data(q_date)
        
        if len(df) < 100:
            continue
            
        # 시장 전체 상관관계 (Spearman)
        corr = df[['roe', 'pbr']].corr(method='spearman').iloc[0, 1]
        
        # 특정 주요 섹터 상관관계
        target_sectors = ['손해보험', '은행', '게임엔터테인먼트', '소프트웨어', '자동차부품']
        sector_corrs = {}
        for sector in target_sectors:
            s_df = df[df['wics_name'] == sector]
            if len(s_df) >= 10:
                s_corr = s_df[['roe', 'pbr']].corr(method='spearman').iloc[0, 1]
                sector_corrs[sector] = s_corr
            else:
                sector_corrs[sector] = np.nan
        
        history_corr.append({
            'date': q_date,
            'market_corr': corr,
            **sector_corrs
        })
        
    df_corr = pd.DataFrame(history_corr)
    df_corr.to_csv(r'c:\Users\Hubnet\antigravity\results\historical_roe_pbr_correlation.csv', index=False, encoding='utf-8-sig')
    
    # 시각화
    plt.figure(figsize=(12, 7))
    plt.plot(df_corr['date'], df_corr['market_corr'], marker='o', linewidth=3, label='시장 전체 (Market)')
    
    for sector in ['손해보험', '은행', '소프트웨어']:
        if sector in df_corr.columns:
            plt.plot(df_corr['date'], df_corr[sector], marker='s', linestyle='--', label=f'{sector}')
            
    plt.title('분기별 ROE-PBR 상관관계 추이 (2024~2025)', fontsize=15)
    plt.xlabel('기준 분기', fontsize=12)
    plt.ylabel('Spearman 상관계수', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(r'c:\Users\Hubnet\antigravity\results\eda_historical_correlation_trend.png')
    
    print("\n상관관계 분석 완료. 결과 저장: results/historical_roe_pbr_correlation.csv 및 eda_historical_correlation_trend.png")
    print(df_corr)

if __name__ == "__main__":
    analyze_correlation()
