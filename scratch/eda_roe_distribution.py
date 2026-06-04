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

def run_roe_distribution():
    conn = get_connection()
    
    # KIS 정보에서 최신 ROE와 업종 정보를 가져옴
    query = """
    WITH industry_base AS (
        SELECT DISTINCT stock_code, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
    ),
    roe_base AS (
        SELECT 
            CASE WHEN shortcode LIKE 'F%' THEN SUBSTRING(shortcode, 2) ELSE shortcode END AS stock_code,
            roe
        FROM company.kis_kospi_info
        UNION ALL
        SELECT 
            shortcode AS stock_code, 
            roe
        FROM company.kis_kosdaq_info
    )
    SELECT 
        ib.wics_name,
        rb.stock_code,
        rb.roe
    FROM roe_base rb
    JOIN industry_base ib ON rb.stock_code = ib.stock_code
    WHERE rb.roe IS NOT NULL
    """
    print("ROE 데이터 로딩 중...")
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("데이터가 없습니다.")
        return

    # 시각화를 위해 극단적인 이상치 제거 (ROE -50% ~ 100% 범위로 제한)
    df_filtered = df[(df['roe'] >= -50) & (df['roe'] <= 100)].copy()

    # 업종별 중앙값 기준 정렬
    order = df_filtered.groupby('wics_name')['roe'].median().sort_values(ascending=False).index
    
    # 1. 박스플롯 시각화
    plt.figure(figsize=(18, 10))
    sns.boxplot(data=df_filtered, x='wics_name', y='roe', order=order, palette='coolwarm')
    plt.xticks(rotation=45, ha='right')
    plt.title('업종별 ROE 분포 현황 (최신 기준, 이상치 일부 제외)', fontsize=15)
    plt.ylabel('ROE (%)')
    plt.xlabel('WICS 업종')
    plt.axhline(0, color='red', linestyle='--', alpha=0.5) # 적자 기준선
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    output_img = r'c:\Users\Hubnet\antigravity\results\eda_roe_distribution.png'
    os.makedirs(os.path.dirname(output_img), exist_ok=True)
    plt.savefig(output_img)
    print(f"차트 저장 완료: {output_img}")

    # 2. 업종별 요약 통계 저장
    summary = df.groupby('wics_name')['roe'].agg(['count', 'mean', 'median', 'std', 'min', 'max']).reset_index()
    summary = summary.sort_values('median', ascending=False)
    summary.to_csv(r'c:\Users\Hubnet\antigravity\results\eda_roe_sector_stats.csv', index=False, encoding='utf-8-sig')
    
    print("\n=== 업종별 ROE 중앙값 상위 10개 ===")
    print(summary[['wics_name', 'count', 'median']].head(10))

if __name__ == "__main__":
    run_roe_distribution()
