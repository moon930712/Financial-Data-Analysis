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

def generate_coupling_viz_v2():
    # 1. 데이터 로드
    df_ts = pd.read_csv(r'c:\Users\Hubnet\antigravity\results\price_pbr_daily_timeseries.csv')
    df_ts['date'] = pd.to_datetime(df_ts['date'])
    
    # 시각화 준비 (업데이트: 2개의 주요 차트로 구성)
    fig = plt.figure(figsize=(14, 12))
    gs = fig.add_gridspec(2, 1)
    
    # --- Chart 1: Market-wide Scatter (Price Chg vs PBR Chg) ---
    ax1 = fig.add_subplot(gs[0, :])
    
    pct_changes = []
    for sector in df_ts['wics_name'].unique():
        s_data = df_ts[df_ts['wics_name'] == sector].sort_values('date')
        if len(s_data) > 2:
            price_chg = (s_data.iloc[-1]['avg_price'] / s_data.iloc[0]['avg_price'] - 1) * 100
            pbr_chg = (s_data.iloc[-1]['avg_pbr'] / s_data.iloc[0]['avg_pbr'] - 1) * 100
            pct_changes.append({'sector': sector, 'price_chg': price_chg, 'pbr_chg': pbr_chg})
    
    df_pct = pd.DataFrame(pct_changes)
    
    sns.regplot(data=df_pct, x='price_chg', y='pbr_chg', ax=ax1, scatter_kws={'alpha':0.5, 's':100}, line_kws={'color':'red'}, ci=None)
    ax1.set_title('전 업종 주가 변동률 vs PBR 변동률 상관관계 (2024~현재)', fontsize=16, pad=15)
    ax1.set_xlabel('주가 변동률 (%)', fontsize=12)
    ax1.set_ylabel('PBR 변동률 (%)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    
    # 특정 업종만 라벨링
    target_labels = ['생물공학', '생명과학도구및서비스', '복합기업', '우주항공과국방', '전기장비', '복합유틸리티', '조선', '카드', '은행']
    for i in range(len(df_pct)):
        sector_name = df_pct.iloc[i]['sector']
        if sector_name in target_labels:
            ax1.annotate(sector_name, (df_pct.iloc[i]['price_chg'], df_pct.iloc[i]['pbr_chg']), 
                         xytext=(5, 5), textcoords='offset points', fontsize=10, weight='bold')

    # --- Chart 2: Coupled Sector Example (대표 사례: 은행) ---
    ax2 = fig.add_subplot(gs[1, :])
    coupled_sector = '은행'
    s_data = df_ts[df_ts['wics_name'] == coupled_sector].sort_values('date')
    
    ax2_twin = ax2.twinx()
    lns1 = ax2.plot(s_data['date'], s_data['avg_price'], color='blue', label='주가 (Price)', linewidth=2.5)
    lns2 = ax2_twin.plot(s_data['date'], s_data['avg_pbr'], color='orange', label='PBR', linewidth=2.5, linestyle='--')
    
    ax2.set_title(f'주가-PBR 동행성(Coupling) 대표 사례: {coupled_sector}', fontsize=14)
    ax2.set_ylabel('주가 (Price)', color='blue', fontsize=12)
    ax2_twin.set_ylabel('PBR', color='orange', fontsize=12)
    
    lns = lns1 + lns2
    labs = [l.get_label() for l in lns]
    ax2.legend(lns, labs, loc='upper left')
    ax2.grid(True, alpha=0.2)
    ax2.set_xlabel('날짜', fontsize=12)

    plt.tight_layout()
    save_path = r'c:\Users\Hubnet\antigravity\results\viz_pbr_price_coupling.png'
    plt.savefig(save_path, dpi=150)
    print(f"Updated Visualization saved to {save_path}")

if __name__ == "__main__":
    generate_coupling_viz_v2()
