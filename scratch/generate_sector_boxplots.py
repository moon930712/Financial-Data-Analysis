import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import font_manager, rc

# 한글 폰트 설정
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
        host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD')
    )

def generate_sector_boxplots():
    conn = get_connection()
    current_date = pd.read_sql_query("SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01", conn).iloc[0,0]
    
    # 1. 전 종목 PBR, ROE 데이터 가져오기 (특정 시점)
    query = """
    WITH current_stocks AS (
        SELECT DISTINCT stock_code, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = %s
    ),
    latest_roe AS (
        SELECT stock_code, roe
        FROM (
            SELECT stock_code, roe, ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY est_dt DESC) as rn
            FROM company.financial_factor_quarterly
            WHERE est_dt <= %s AND roe IS NOT NULL
        ) t WHERE rn = 1
    )
    SELECT 
        s.wics_name as sector,
        fb.pbr,
        r.roe
    FROM current_stocks s
    JOIN company.krx_stocks_fundamental_info fb ON s.stock_code = fb.code AND fb.date = %s
    LEFT JOIN latest_roe r ON s.stock_code = r.stock_code
    WHERE fb.pbr > 0 AND fb.pbr < 10 -- 이상치 제거
    """
    df = pd.read_sql_query(query, conn, params=(current_date, current_date, current_date))
    conn.close()
    
    # 2. 업종별 개수가 너무 적은 것 제외하고 상위 15개 섹터 선정 (ROE 변동성 확인용)
    top_sectors = df['sector'].value_counts().head(15).index.tolist()
    df_plot = df[df['sector'].isin(top_sectors)]
    
    # 3. 시각화 (PBR & ROE Boxplot)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))
    
    sns.boxplot(data=df_plot, x='sector', y='pbr', ax=ax1, palette='Set3')
    ax1.set_title('업종별 PBR 분포 (Boxplot) - 왜 업종별로 분석해야 하는가?', fontsize=16)
    ax1.set_xlabel('')
    ax1.tick_params(axis='x', rotation=45)
    
    sns.boxplot(data=df_plot, x='sector', y='roe', ax=ax2, palette='Set2')
    ax2.set_title('업종별 ROE 분포 (Boxplot) - 수익성 기초 체력의 차이', fontsize=16)
    ax2.set_xlabel('')
    ax2.tick_params(axis='x', rotation=45)
    ax2.set_ylim(-0.1, 0.3) # ROE 가독성 위해 범위 제한
    
    plt.tight_layout()
    save_path = r'c:\Users\Hubnet\antigravity\results\viz_sector_distribution_boxplot.png'
    plt.savefig(save_path, dpi=150)
    print(f"Sector distribution boxplots saved to {save_path}")

if __name__ == "__main__":
    generate_sector_boxplots()
