import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 폰트 설정 (한글 깨짐 방지)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

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

def run_pbr_return_correlation():
    conn = get_connection()
    
    # 1. 시계열 데이터 수집 (업종별 평균 PBR + 종가)
    # 2024년 이후 가격 데이터가 있으므로 2024년부터 분석
    query = """
    WITH stats AS (
        SELECT 
            s.date,
            s.wics_name,
            AVG(f.pbr) as avg_pbr,
            AVG(s.close) as avg_price
        FROM visual.vsl_anly_stocks_price_subindex01 s
        JOIN company.krx_stocks_fundamental_info f ON s.stock_code = f.code AND s.date = f.date
        WHERE s.date >= '2024-01-01'
        GROUP BY s.date, s.wics_name
    )
    SELECT * FROM stats ORDER BY wics_name, date
    """
    print("성관관계 분석용 데이터 로딩 중...")
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("데이터가 없습니다.")
        return

    # 2. 6개월(약 120영업일) 후 수익률 계산
    results = []
    industries = df['wics_name'].unique()
    
    for ind in industries:
        ind_df = df[df['wics_name'] == ind].sort_values('date')
        ind_df['future_return_6m'] = ind_df['avg_price'].shift(-120) / ind_df['avg_price'] - 1
        results.append(ind_df.dropna())
    
    corr_df = pd.concat(results)
    
    # 3. 상관관계 분석
    correlation = corr_df['avg_pbr'].corr(corr_df['future_return_6m'])
    print(f"\n[통계 결과] PBR과 6개월 후 수익률의 상관계수: {correlation:.4f}")
    
    # 4. 시각화 (산점도 + 회귀선)
    plt.figure(figsize=(10, 7))
    sns.regplot(data=corr_df, x='avg_pbr', y='future_return_6m', scatter_kws={'alpha':0.3, 'color':'blue'}, line_kws={'color':'red'})
    plt.title('업종별 PBR vs 6개월 후 수익률 상관관계 (2024년 이후)', fontsize=15)
    plt.xlabel('매수 시점 PBR (배)')
    plt.ylabel('6개월 후 수익률 (%)')
    plt.grid(True, linestyle='--', alpha=0.5)
    
    output_img = r'c:\Users\Hubnet\antigravity\results\eda_pbr_return_correlation.png'
    os.makedirs(os.path.dirname(output_img), exist_ok=True)
    plt.savefig(output_img)
    print(f"상관관계 차트 저장 완료: {output_img}")

    # 5. PBR 구간별 평균 수익률 분석
    corr_df['pbr_bin'] = pd.qcut(corr_df['avg_pbr'], 5, labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'])
    bin_perf = corr_df.groupby('pbr_bin')['future_return_6m'].mean() * 100
    
    print("\n=== PBR 구간별 평균 6개월 수익률 ===")
    print(bin_perf)

if __name__ == "__main__":
    run_pbr_return_correlation()
