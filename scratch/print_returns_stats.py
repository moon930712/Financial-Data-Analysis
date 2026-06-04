import pandas as pd

excel_path = 'pattern_consumer_stats_master.xlsx'
df_raw = pd.read_excel(excel_path, sheet_name='Raw Data')
df_stats = pd.read_excel(excel_path, sheet_name='Pattern Stats')

# 상위 10개 패턴 리스트
patterns = df_stats.head(10)['Pattern'].tolist()

print("=== 상위 10개 패턴의 진입 후 일자별(D+1 ~ D+5) 수익률 평균 및 중앙값 ===")

for pattern in patterns:
    df_p = df_raw[df_raw['Pattern'] == pattern]
    if df_p.empty:
        continue
    
    print(f"\n★ 패턴: {pattern} (Count: {len(df_p)})")
    
    for day in range(1, 6):
        col = f'D+{day} Return (%)'
        avg_ret = df_p[col].mean()
        med_ret = df_p[col].median()
        print(f"  - D+{day}: 평균 {avg_ret:.2f}% / 중앙값 {med_ret:.2f}%")
