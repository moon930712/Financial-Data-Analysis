import os
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

def generate_positioning_map():
    # 1. 데이터 로드
    df = pd.read_csv(r'c:\Users\Hubnet\antigravity\results\pbr_price_roe_viz_data.csv')
    
    # 2. 기준선 (Median) 계산
    pbr_median = df['median_pbr'].median()
    roe_median = df['median_roe'].median()
    
    print(f"PBR Median: {pbr_median:.2f}, ROE Median: {roe_median:.4f}")
    
    # 3. 시각화
    plt.figure(figsize=(14, 10))
    
    # 배경 사분면 색상 및 텍스트 설정
    # Q1: Golden Area (Low PBR, High ROE)
    plt.axvspan(0, pbr_median, ymin=0.5, ymax=1, color='gold', alpha=0.1)
    plt.text(pbr_median*0.3, df['median_roe'].max()*0.9, '1사분면: Golden Area\n(저평가 우량)', fontsize=15, color='darkgoldenrod', weight='bold')
    
    # Q2: Premium/Growth (High PBR, High ROE)
    plt.axvspan(pbr_median, df['median_pbr'].max()*1.1, ymin=0.5, ymax=1, color='green', alpha=0.05)
    plt.text(pbr_median*1.5, df['median_roe'].max()*0.9, '2사분면: Premium\n(시장 주도주)', fontsize=15, color='darkgreen', weight='bold')
    
    # Q3: Value Trap (Low PBR, Low ROE)
    plt.axvspan(0, pbr_median, ymin=0, ymax=0.5, color='grey', alpha=0.1)
    plt.text(pbr_median*0.3, df['median_roe'].min()*0.5, '3사분면: Value Trap\n(자본 효율성 낮음)', fontsize=15, color='grey', weight='bold')
    
    # Q4: Speculative/Avoid (High PBR, Low ROE)
    plt.axvspan(pbr_median, df['median_pbr'].max()*1.1, ymin=0, ymax=0.5, color='red', alpha=0.05)
    plt.text(pbr_median*1.5, df['median_roe'].min()*0.5, '4사분면: Avoid\n(고평가/저성장)', fontsize=15, color='darkred', weight='bold')

    # 산점도
    sns.scatterplot(data=df, x='median_pbr', y='median_roe', size='median_roe', sizes=(50, 500), alpha=0.6, hue='median_roe', palette='viridis')
    
    # 기준선 (Crosshair)
    plt.axvline(x=pbr_median, color='black', linestyle='--', linewidth=1)
    plt.axhline(y=roe_median, color='black', linestyle='--', linewidth=1)
    
    # 주요 업종 라벨링 (각 사분면 대표주)
    # ROE가 높거나 PBR이 아주 낮은 업종 위주로 라벨 표시
    for i in range(len(df)):
        row = df.iloc[i]
        # 임의의 기준(상위권)으로 라벨링하여 가독성 확보
        if (row['median_roe'] > roe_median * 1.5) or (row['median_pbr'] < pbr_median * 0.5) or (row['median_pbr'] > pbr_median * 2.5):
            plt.annotate(row['wics_name'], (row['median_pbr'], row['median_roe']), xytext=(5, 5), textcoords='offset points', fontsize=11)

    plt.title('업종별 PBR-ROE 포지셔닝 맵 (Positioning Map)', fontsize=20, pad=20)
    plt.xlabel('PBR (Valuation)', fontsize=14)
    plt.ylabel('ROE (Profitability)', fontsize=14)
    plt.grid(True, alpha=0.2)
    plt.legend(title='ROE Level', loc='upper right')
    
    save_path = r'c:\Users\Hubnet\antigravity\results\viz_pbr_roe_positioning_map.png'
    plt.savefig(save_path, dpi=150)
    print(f"Positioning map saved to {save_path}")

if __name__ == "__main__":
    generate_positioning_map()
