import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import font_manager, rc

# 폰트 설정
try:
    font_path = "C:/Windows/Fonts/malgun.ttf"
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    rc('font', family=font_name)
    plt.rcParams['axes.unicode_minus'] = False
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

def run_individual_eda():
    conn = get_connection()
    
    # 분석 시나리오: 약 1년 전('2024-04-01')의 PBR과 ROE를 바탕으로 가성비 수치를 계산하고,
    # 그 후 1년간의('2025-04-01') 수익률과 어떤 상관관계가 있는지 전수 조사합니다.
    target_date = '2024-04-01'
    future_date = '2025-04-01'
    
    query = f"""
    WITH industry_base AS (
        SELECT DISTINCT stock_code, stock_name, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{target_date}'
    ),
    fundamental_base AS (
        SELECT code AS stock_code, pbr
        FROM company.krx_stocks_fundamental_info
        WHERE date = '{target_date}'
    ),
    roe_base AS (
        SELECT koreanname AS stock_name, roe 
        FROM company.kis_kospi_info
        UNION ALL
        SELECT koreanname AS stock_name, roe 
        FROM company.kis_kosdaq_info
    ),
    price_start AS (
        SELECT stock_code, close as price_start
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{target_date}'
    ),
    price_end AS (
        SELECT stock_code, close as price_end
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{future_date}'
    )
    SELECT 
        ib.wics_name
        , ib.stock_name
        , ib.stock_code
        , rb.roe
        , fb.pbr
        , fb.pbr / NULLIF(rb.roe, 0) AS pbr_per_roe
        , (pe.price_end / ps.price_start - 1) * 100 as return_1yr
    FROM industry_base ib
    JOIN roe_base rb ON ib.stock_name = rb.stock_name
    JOIN fundamental_base fb ON ib.stock_code = fb.stock_code
    JOIN price_start ps ON ib.stock_code = ps.stock_code
    JOIN price_end pe ON ib.stock_code = pe.stock_code
    WHERE rb.roe > 0 
      AND fb.pbr > 0
    """
    
    print("전수 데이터(약 2,600종목) 수집 중...")
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"데이터 로드 완료: 총 {len(df)}개 종목 분석")

    # 극단적인 아웃라이어 제거 (가성비가 너무 이상하게 잡힌 종목들 필터링)
    # ROE > 0 조건은 쿼리에 포함됨. PBR_per_ROE가 너무 크거나 작으면 분석에서 제외.
    q_low = df['pbr_per_roe'].quantile(0.01)
    q_high = df['pbr_per_roe'].quantile(0.95) # 최악의 가성비 종목들 중 상위 5% 제외 (왜곡 방지)
    
    df_clean = df[(df['pbr_per_roe'] >= q_low) & (df['pbr_per_roe'] <= q_high) & (df['return_1yr'].abs() < 500)].copy()

    # 가성비 '순위(Quintile)' 부여: 1분위가 가성비 가장 좋음(pbr_per_roe 낮음), 5분위가 가장 나쁨
    df_clean['Quintile'] = pd.qcut(df_clean['pbr_per_roe'], 5, labels=['Q1(최고 가성비)', 'Q2', 'Q3', 'Q4', 'Q5(최악 가성비)'])

    # 1. 분위별 평균 수익률 비교 시각화
    summary = df_clean.groupby('Quintile')['return_1yr'].mean().reset_index()
    
    plt.figure(figsize=(10, 6))
    ax = sns.barplot(data=summary, x='Quintile', y='return_1yr', palette='Blues_r')
    plt.title('ROE/PBR 가성비 수준별 1년 후 평균 수익률 (Q1~Q5)', fontsize=15)
    plt.xlabel('가성비 그룹 (Q1: 가장 저렴하고 돈 잘 버는 그룹)')
    plt.ylabel('1년 평균 수익률 (%)')
    plt.axhline(0, color='red', linestyle='--')
    
    # 값 표기
    for p in ax.patches:
        ax.annotate(f"{p.get_height():.1f}%", (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha='center', va='center', fontsize=12, color='black', xytext=(0, 10), 
                    textcoords='offset points')
        
    out_path1 = r'c:\Users\Hubnet\antigravity\results\eda_individual_quantile_performance.png'
    os.makedirs(os.path.dirname(out_path1), exist_ok=True)
    plt.savefig(out_path1, dpi=150)
    print(f"가성비 분위별 수익률 차트 저장 완료: {out_path1}")

    # 2. 산점도 시각화 (가성비 지표 vs 수익률)
    plt.figure(figsize=(10, 6))
    sns.regplot(data=df_clean, x='pbr_per_roe', y='return_1yr', scatter_kws={'alpha':0.3, 's':10}, line_kws={'color':'red'})
    plt.title('개별 종목 가성비(PBR_per_ROE)와 1년 수익률의 상관관계', fontsize=15)
    plt.xlabel('PBR per ROE (점수가 낮을수록 가성비 좋음)')
    plt.ylabel('1년 후 수익률 (%)')
    plt.grid(True, linestyle='--', alpha=0.5)
    
    out_path2 = r'c:\Users\Hubnet\antigravity\results\eda_individual_scatter.png'
    plt.savefig(out_path2, dpi=150)
    print(f"산점도 저장 완료: {out_path2}")
    
    # 데이터를 CSV로 추출
    csv_path = r'c:\Users\Hubnet\antigravity\results\individual_stock_efficiency_data.csv'
    df_clean.sort_values('pbr_per_roe').to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"전체 분석 데이터 CSV 저장 완료: {csv_path}")

if __name__ == "__main__":
    run_individual_eda()
