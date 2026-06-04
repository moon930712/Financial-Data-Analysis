import os
import psycopg2
import pandas as pd
import numpy as np

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

def analyze_pbr_price_coupling():
    conn = get_connection()
    
    # 2024년 이후 모든 섹터의 일별 종가 및 PBR(평균) 가져오기
    # 데이터가 많으므로 효율적인 쿼리 필요
    query = """
    SELECT ib.wics_name, ib.date, AVG(ib.close) as avg_price, AVG(fb.pbr) as avg_pbr
    FROM visual.vsl_anly_stocks_price_subindex01 ib
    JOIN company.krx_stocks_fundamental_info fb ON ib.stock_code = fb.code AND ib.date = fb.date
    WHERE ib.date >= '2024-01-01'
    GROUP BY ib.wics_name, ib.date
    ORDER BY ib.wics_name, ib.date
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 섹터별 상관관계 계산
    corrs = []
    for sector in df['wics_name'].unique():
        s_df = df[df['wics_name'] == sector]
        if len(s_df) > 10:
            c = s_df['avg_price'].corr(s_df['avg_pbr'])
            corrs.append({'sector': sector, 'price_pbr_corr': c})
            
    df_corr = pd.DataFrame(corrs).sort_values('price_pbr_corr', ascending=False)
    
    # 상관관계가 낮은 섹터(디커플링)와 높은 섹터 추출
    print("--- Price-PBR Coupling Analysis (Top 10) ---")
    print(df_corr.head(10))
    print("\n--- Price-PBR Decoupling Analysis (Bottom 10) ---")
    print(df_corr.tail(10))
    
    df_corr.to_csv(r'c:\Users\Hubnet\antigravity\results\price_pbr_coupling_analysis.csv', index=False, encoding='utf-8-sig')
    
    # 특정 디커플링 사례 (수익성 개선으로 PBR이 눌린 경우) 연구를 위해 데이터 저장
    df.to_csv(r'c:\Users\Hubnet\antigravity\results\price_pbr_daily_timeseries.csv', index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    analyze_pbr_price_coupling()
