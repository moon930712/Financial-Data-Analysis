import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('scratch/theme_6_features.csv')

# Split groups
df_success = df[df['target'] == 1]
df_fail = df[df['target'] == 0]

print("=== [단계 2] 성공군(6->1,2) vs 실패군(6->6) 지표 비교 ===")
print(f"성공군 수: {len(df_success)} | 실패군 수: {len(df_fail)}\n")

features = ['volume_spike', 'avg_rsi', 'avg_disparity_20', 'total_sm_flow']

for feat in features:
    s_mean = df_success[feat].mean()
    s_median = df_success[feat].median()
    
    f_mean = df_fail[feat].mean()
    f_median = df_fail[feat].median()
    
    print(f"[{feat}]")
    print(f"  - 성공군: 평균 {s_mean:.2f} | 중앙값 {s_median:.2f}")
    print(f"  - 실패군: 평균 {f_mean:.2f} | 중앙값 {f_median:.2f}")
    if f_median != 0:
        ratio = (s_median / f_median - 1) * 100
        print(f"  => 성공군이 중앙값 기준 {ratio:+.1f}% 차이")
    print()

# MACD Trend
s_macd_improving = df_success['macd_improving'].mean() * 100
f_macd_improving = df_fail['macd_improving'].mean() * 100
print("[macd_improving (MACD 상방 전환 비율)]")
print(f"  - 성공군: {s_macd_improving:.1f}%")
print(f"  - 실패군: {f_macd_improving:.1f}%")

