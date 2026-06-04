import pandas as pd

df_raw = pd.read_excel('pattern_consumer_stats_master.xlsx', sheet_name='Raw Data')

patterns = [
    '4등급 -> 3등급 -> 1등급',
    '2등급 -> 5등급 -> 5등급',
    '6등급 -> 4등급 -> 1등급',
    '4등급 -> 2등급 -> 2등급'
]

print("=== 고급 퀀트 지표 분석 결과 ===")
for p in patterns:
    df_p = df_raw[df_raw['Pattern'] == p]
    if df_p.empty:
        continue
    ret = df_p['D+5 Return (%)']
    
    # 5일간의 누적 수익률이 -5% 이하로 떨어지는 큰 손실 비중
    large_loss_ratio = (ret <= -5.0).mean() * 100
    
    # 변동성 (표준편차)
    volatility = ret.std()
    
    print(f"\n★ 패턴: {p}")
    print(f"  - 표본 수: {len(df_p)}개")
    print(f"  - 평균 수익률: {ret.mean():.2f}% / 중앙값 수익률: {ret.median():.2f}%")
    print(f"  - 표준편차 (변동성): {volatility:.2f}%")
    print(f"  - 최대 수익률 (Max): {ret.max():.2f}% / 최소 수익률 (Min): {ret.min():.2f}%")
    print(f"  - 5% 이상 큰 손실 확률 (Risk Ratio): {large_loss_ratio:.2f}%")
    print(f"  - 승률 (>0%): {(ret > 0).mean()*100:.2f}%")
