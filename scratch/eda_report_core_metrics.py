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

def run_core_eda():
    conn = get_connection()
    
    # 1. 2024년 1월 1일 이후 업종별 PBR 시계열 데이터 수집
    query_pbr = """
    SELECT 
        s.date,
        s.wics_name,
        AVG(f.pbr) as avg_pbr
    FROM visual.vsl_anly_stocks_price_subindex01 s
    JOIN company.krx_stocks_fundamental_info f ON s.stock_code = f.code AND s.date = f.date
    WHERE s.date >= '2024-01-01'
    GROUP BY s.date, s.wics_name
    ORDER BY s.wics_name, s.date
    """
    print("2024년 이후 PBR 데이터 로딩 중...")
    df_pbr = pd.read_sql_query(query_pbr, conn)
    
    # 2. 최신 ROE 데이터 수집 (중앙값 사용)
    query_roe = """
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
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rb.roe) as industry_roe_median
    FROM roe_base rb
    JOIN industry_base ib ON rb.stock_code = ib.stock_code
    WHERE rb.roe IS NOT NULL
    GROUP BY ib.wics_name
    """
    print("최신 ROE 중앙값 데이터 로딩 중...")
    df_roe = pd.read_sql_query(query_roe, conn)
    conn.close()
    
    # 3. 업종별 역사적 통계 산출 (2024년 이후)
    sector_stats = df_pbr.groupby('wics_name')['avg_pbr'].agg(['min', 'max', 'mean', 'last']).reset_index()
    sector_stats.columns = ['wics_name', '2024_min', '2024_max', '2024_avg', 'current_pbr']
    
    # 현재 위치 백분위 (Range Percentile) - 낮을수록 역사적 저점
    sector_stats['pbr_pos_pct'] = (sector_stats['current_pbr'] - sector_stats['2024_min']) / (sector_stats['2024_max'] - sector_stats['2024_min']) * 100
    
    # ROE 결합
    final_df = sector_stats.merge(df_roe, on='wics_name', how='inner')
    
    # 가성비 지표 (ROE / PBR)
    final_df['efficiency'] = final_df['industry_roe_median'] / final_df['current_pbr']
    
    # 최고점 대비 하락 정도 (낮을수록 많이 하락)
    final_df['pbr_to_max_ratio'] = final_df['current_pbr'] / final_df['2024_max']
    
    # 결과 저장
    final_df.to_csv(r'c:\Users\Hubnet\antigravity\results\eda_core_metrics_summary.csv', index=False, encoding='utf-8-sig')
    print("통계 요약 저장 완료: eda_core_metrics_summary.csv")

    # 4. 시각화 1: 업종별 PBR 밴드 (2024년 이후)
    plt.figure(figsize=(18, 10))
    # 정렬: 과거 최고점 대비 현재 PBR이 낮은 순 (하락률이 큰 순)
    plot_order = final_df.sort_values('pbr_to_max_ratio')['wics_name']
    
    sns.pointplot(data=df_pbr, x='wics_name', y='avg_pbr', order=plot_order, join=False, color='gray', markers='_', scale=0.5, alpha=0.3)
    # 현재 값 표시
    sns.scatterplot(data=final_df, x='wics_name', y='current_pbr', color='red', s=100, label='최신 PBR')
    # 2024 역사적 범위 표시 (최저, 최고)
    plt.vlines(x=range(len(plot_order)), ymin=final_df.sort_values('pbr_pos_pct')['2024_min'], ymax=final_df.sort_values('pbr_pos_pct')['2024_max'], color='black', alpha=0.3, label='2024 역사적 범위 (Min-Max)')
    
    plt.xticks(rotation=45, ha='right')
    plt.title('2024년 이후 업종별 PBR 밴드 및 현재 위치 (오른쪽으로 갈수록 역사적 고점)', fontsize=15)
    plt.ylabel('PBR (배)')
    plt.legend()
    plt.tight_layout()
    plt.savefig(r'c:\Users\Hubnet\antigravity\results\eda_sector_pbr_band.png')
    print("PBR 밴드 차트 저장 완료: eda_sector_pbr_band.png")

    # 5. 시각화 2: ROE 대비 PBR 효율성 (가성비 매트릭스)
    plt.figure(figsize=(14, 10))
    # ROE가 너무 큰 음수이거나 양수인 경우 시각화를 위해 필터링
    df_matrix = final_df[(final_df['industry_roe_median'] > -30) & (final_df['industry_roe_median'] < 50)].copy()
    scatter = plt.scatter(df_matrix['industry_roe_median'], df_matrix['current_pbr'], s=100, alpha=0.5, c=df_matrix['pbr_pos_pct'], cmap='coolwarm_r')
    plt.colorbar(scatter, label='PBR 역사적 위치 (파란색일수록 바닥)')
    
    for i, txt in enumerate(df_matrix['wics_name']):
        plt.annotate(txt, (df_matrix['industry_roe_median'].iloc[i], df_matrix['current_pbr'].iloc[i]), fontsize=9, alpha=0.8)

    plt.axvline(df_matrix['industry_roe_median'].median(), color='gray', linestyle='--', alpha=0.3)
    plt.axhline(df_matrix['current_pbr'].median(), color='gray', linestyle='--', alpha=0.3)
    
    plt.title('업종별 ROE-PBR 가성비 매트릭스 (우하단: 저평가 우량 섹터)', fontsize=15)
    plt.xlabel('평균 ROE (%)')
    plt.ylabel('최신 PBR (배)')
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.savefig(r'c:\Users\Hubnet\antigravity\results\eda_roe_efficiency_matrix.png')
    print("가성비 매트릭스 차트 저장 완료: eda_roe_efficiency_matrix.png")

if __name__ == "__main__":
    run_core_eda()
