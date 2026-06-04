import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from matplotlib import font_manager, rc

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

def run_eda_pbr():
    conn = get_connection()
    
    # 1. 과년 3년치 데이터 수집 (업종 + PBR)
    # Price subindex01에서 업종명을 가져오고, krx_fundamental_info에서 PBR을 가져옴
    query = """
    WITH industry_base AS (
        SELECT DISTINCT stock_code, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
    )
    SELECT 
        f.date,
        ib.wics_name,
        f.code,
        f.pbr
    FROM company.krx_stocks_fundamental_info f
    JOIN industry_base ib ON f.code = ib.stock_code
    WHERE f.date >= CURRENT_DATE - INTERVAL '3 years'
      AND f.pbr > 0 AND f.pbr < 15
    """
    print("데이터 로딩 중...")
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("데이터가 없습니다.")
        return

    # 2. 업종별 현재 위치 산출 (가장 최근 날짜)
    latest_date = df['date'].max()
    current_df = df[df['date'] == latest_date]
    
    # 정렬 기준: 업종별 PBR 중앙값 산출
    order = current_df.groupby('wics_name')['pbr'].median().sort_values().index
    
    # 3. 박스플롯 시각화 (업종별 PBR 분포 차이 증명)
    plt.figure(figsize=(18, 10)) # 가독성을 위해 가로 폭 확대
    sns.boxplot(data=current_df, x='wics_name', y='pbr', order=order, palette='vlag')
    plt.xticks(rotation=45, ha='right')
    plt.title(f'업종별 PBR 분포 현황 (기준일: {latest_date})', fontsize=15)
    plt.ylabel('PBR (배)')
    plt.xlabel('WICS 업종')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    output_img = r'c:\Users\Hubnet\antigravity\results\eda_pbr_distribution.png'
    os.makedirs(os.path.dirname(output_img), exist_ok=True)
    plt.savefig(output_img)
    print(f"차트 저장 완료: {output_img}")

    # 4. 역사적 위치(Percentile) 산출
    # 업종별 일자별 평균 PBR 시계열 생성
    ts_industry = df.groupby(['date', 'wics_name'])['pbr'].median().unstack()
    
    summary_stats = []
    for col in ts_industry.columns:
        current_val = ts_industry[col].iloc[-1]
        hist_data = ts_industry[col].dropna()
        
        # 현재 값이 역사적 분포에서 어느 위치(백분위)인지 계산
        percentile = (hist_data < current_val).mean() * 100
        
        summary_stats.append({
            '업종명': col,
            '현재 PBR(중앙값)': round(current_val, 3),
            '3년 평균': round(hist_data.mean(), 3),
            '3년 최저': round(hist_data.min(), 3),
            '3년 최고': round(hist_data.max(), 3),
            '역사적 백분위(%)': round(percentile, 1)
        })
    
    summary_df = pd.DataFrame(summary_stats).sort_values('역사적 백분위(%)')
    
    # 5. 결과 저장 및 출력
    summary_df.to_csv(r'c:\Users\Hubnet\antigravity\results\eda_pbr_historical_stats.csv', index=False, encoding='utf-8-sig')
    print("\n=== 업종별 역사적 PBR 위치 (낮을수록 억눌려 있음) ===")
    print(summary_df.head(10))

if __name__ == "__main__":
    run_eda_pbr()
