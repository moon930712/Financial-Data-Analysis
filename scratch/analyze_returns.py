import pandas as pd
import numpy as np

def main():
    print("Loading data...")
    df = pd.read_excel('backtest_extract_target_patterns_with_rsi_features.xlsx', sheet_name='Raw Data')
    
    # Calculate Max 5-Day Return
    return_cols = ['D+1 Return (%)', 'D+2 Return (%)', 'D+3 Return (%)', 'D+4 Return (%)', 'D+5 Return (%)']
    df['Max_Return_5D'] = df[return_cols].max(axis=1)
    
    features = ['거래대금', 'Volume Spike', 'Smart Money', '20MA 이격도', '당일 시가 대비 상승률 (%)', 'D+day rsi']
    targets = ['D+5 Return (%)', 'Max_Return_5D']
    
    print("\n" + "="*50)
    print("1. Correlation Analysis (상관관계 분석)")
    print("*" + " 1.0에 가까울수록 강한 양의 상관관계 (비례)")
    print("*" + " -1.0에 가까울수록 강한 음의 상관관계 (반비례)")
    print("*" + " 0에 가까울수록 관계 없음")
    print("="*50)
    
    # Calculate Pearson correlation
    corr_matrix = df[features + targets].corr(method='pearson')
    print("\n[Pearson Correlation with Returns]")
    corr_summary = corr_matrix.loc[features, targets].round(3)
    print(corr_summary)
    
    print("\n" + "="*50)
    print("2. Feature Quantile Analysis (상위 50% vs 하위 50% 수익률 비교)")
    print("="*50)
    
    for f in features:
        if df[f].isna().all(): continue
        median_val = df[f].median()
        high_group = df[df[f] >= median_val]
        low_group = df[df[f] < median_val]
        
        high_avg_d5 = high_group['D+5 Return (%)'].mean()
        low_avg_d5 = low_group['D+5 Return (%)'].mean()
        high_win = (high_group['D+5 Return (%)'] > 0).mean() * 100
        low_win = (low_group['D+5 Return (%)'] > 0).mean() * 100
        
        print(f"\n[{f}] 기준 (중앙값: {median_val:,.2f})")
        print(f"  - {f} 상위 50% 그룹: 평균 D+5 수익률 = {high_avg_d5:,.2f}% / 승률 = {high_win:.1f}% (N={len(high_group)})")
        print(f"  - {f} 하위 50% 그룹: 평균 D+5 수익률 = {low_avg_d5:,.2f}% / 승률 = {low_win:.1f}% (N={len(low_group)})")

if __name__ == '__main__':
    main()
