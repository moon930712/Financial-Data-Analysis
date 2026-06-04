import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 폰트 설정
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

def run_roe_pbr_joint_analysis():
    conn = get_connection()
    
    # 데이터 수집: 최신 ROE, PBR, 그리고 수익률 성과 측정을 위한 과거 데이터(예: 6개월 전 시점 기준)
    # 여기서는 '2025-04-01' 시점을 기준으로 그 당시의 ROE/PBR과 이후 6개월 성과를 분석함
    target_date = '2025-04-01'
    future_date = '2025-10-01'
    
    query = f"""
    WITH industry_base AS (
        SELECT DISTINCT stock_code, stock_name, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{target_date}'
    ),
    fundamental_base AS (
        SELECT code AS stock_code, pbr, per
        FROM company.krx_stocks_fundamental_info
        WHERE date = '{target_date}'
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
        ib.wics_name,
        ib.stock_name,
        rb.roe,
        fb.pbr,
        (pe.price_end / ps.price_start - 1) * 100 as return_6m
    FROM industry_base ib
    JOIN roe_base rb ON ib.stock_code = rb.stock_code
    JOIN fundamental_base fb ON ib.stock_code = fb.stock_code
    JOIN price_start ps ON ib.stock_code = ps.stock_code
    JOIN price_end pe ON ib.stock_code = pe.stock_code
    WHERE rb.roe IS NOT NULL AND fb.pbr IS NOT NULL
    """
    print(f"{target_date} 기준 데이터 수집 중...")
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("데이터가 없습니다.")
        return

    # 이상치 필터링 (시각화 목적: ROE -50~100, PBR 0~10)
    df_plot = df[(df['roe'] >= -50) & (df['roe'] <= 100) & (df['pbr'] > 0) & (df['pbr'] <= 10)].copy()

    # 1. PBR-ROE 산점도 (수수익률 색상 입히기)
    plt.figure(figsize=(14, 10))
    scatter = plt.scatter(df_plot['roe'], df_plot['pbr'], c=df_plot['return_6m'], cmap='RdYlGn', alpha=0.6, s=50)
    plt.colorbar(scatter, label='6개월 후 수익률 (%)')
    
    # 4분면 가이드라인 (평균값 기준)
    roe_mean = df_plot['roe'].mean()
    pbr_mean = df_plot['pbr'].mean()
    plt.axvline(roe_mean, color='blue', linestyle='--', alpha=0.3)
    plt.axhline(pbr_mean, color='blue', linestyle='--', alpha=0.3)
    
    plt.text(roe_mean + 5, pbr_mean + 2, '고평가 성장주 (High PBR, High ROE)', fontsize=10, alpha=0.7)
    plt.text(roe_mean - 45, pbr_mean - 0.5, '소외된 가치주 (Low PBR, Low ROE)', fontsize=10, alpha=0.7)
    plt.text(roe_mean + 5, pbr_mean - 0.5, '★ 저평가 우량주 (Low PBR, High ROE)', fontsize=12, color='darkgreen', fontweight='bold')
    
    plt.title(f'PBR-ROE 매트릭스 분석 (기준일: {target_date}, 수익률: 6개월)', fontsize=15)
    plt.xlabel('ROE (%)')
    plt.ylabel('PBR (배)')
    plt.grid(True, linestyle='--', alpha=0.3)
    
    output_img = r'c:\Users\Hubnet\antigravity\results\eda_pbr_roe_joint_scatter.png'
    os.makedirs(os.path.dirname(output_img), exist_ok=True)
    plt.savefig(output_img)
    print(f"산점도 저장 완료: {output_img}")

    # 2. 업종별 PBR/ROE 요약 (버블 차트용)
    ind_summary = df_plot.groupby('wics_name').agg({
        'roe': 'median',
        'pbr': 'median',
        'return_6m': 'mean'
    }).reset_index()

    plt.figure(figsize=(16, 11))
    sns.scatterplot(data=ind_summary, x='roe', y='pbr', size='return_6m', hue='return_6m', palette='RdYlGn', sizes=(100, 1000), legend=False)
    
    for i in range(ind_summary.shape[0]):
        plt.text(ind_summary.roe[i], ind_summary.pbr[i]+0.1, ind_summary.wics_name[i], fontsize=9, ha='center')

    plt.title('업종별 PBR-ROE 및 수익률 분포 (버블 크기: 수익률)', fontsize=15)
    plt.xlabel('ROE 중앙값 (%)')
    plt.ylabel('PBR 중앙값 (배)')
    plt.grid(True, linestyle='--', alpha=0.3)
    
    output_img_ind = r'c:\Users\Hubnet\antigravity\results\eda_pbr_roe_industry_bubble.png'
    plt.savefig(output_img_ind)
    print(f"업종별 버블차트 저장 완료: {output_img_ind}")

    # 3. 전략적 종목군(저PBR-고ROE) 리스트 저장
    under_gems = df[(df['roe'] > df['roe'].median()) & (df['pbr'] < df['pbr'].median())].sort_values('return_6m', ascending=False)
    under_gems.to_csv(r'c:\Users\Hubnet\antigravity\results\eda_pbr_roe_undervalued_gems.csv', index=False, encoding='utf-8-sig')
    print(f"저평가 우량주 리스트 저장 완료")

if __name__ == "__main__":
    run_roe_pbr_joint_analysis()
