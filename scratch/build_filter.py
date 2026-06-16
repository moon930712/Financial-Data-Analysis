import pandas as pd

# Load data
df = pd.read_csv('scratch/theme_6_features.csv')

print("=== [단계 3] 예측 필터 조건 백테스트 ===")
print("전체 6등급 발생 건수:", len(df))
print("실제 1~2등급 점프(Success) 건수:", len(df[df['target'] == 1]))
print(f"기본 점프 확률(Base Rate): {len(df[df['target'] == 1]) / len(df) * 100:.2f}%\n")

# Apply Filter based on Step 2 insights:
# 1. Quiet Volume (volume_spike < 0.8)
# 2. Oversold (avg_rsi < 48)
# 3. Compressed under 20MA (avg_disparity_20 < 99)
# 4. Momentum turning (macd_improving == 1)

df_filtered = df[
    (df['volume_spike'] < 0.8) &
    (df['avg_rsi'] < 48) &
    (df['avg_disparity_20'] < 99) &
    (df['macd_improving'] == 1)
]

print("=== 필터 적용 후 결과 ===")
total_filtered = len(df_filtered)
success_filtered = len(df_filtered[df_filtered['target'] == 1])

if total_filtered > 0:
    win_rate = success_filtered / total_filtered * 100
    print(f"필터에 걸린 총 건수(매수 시그널 발생): {total_filtered}건")
    print(f"그 중 실제로 1~2등급 점프 성공: {success_filtered}건")
    print(f"🎯 필터 적중률(Win Rate): {win_rate:.2f}%")
    print(f"📈 기본 확률 대비 향상도: +{win_rate - (len(df[df['target'] == 1]) / len(df) * 100):.2f}%p")
else:
    print("조건에 맞는 결과가 없습니다.")

