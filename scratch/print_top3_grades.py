import pandas as pd

excel_path = 'pattern_grade_transition.xlsx'
df_dist = pd.read_excel(excel_path, sheet_name='Distribution')

# 상위 10개 패턴 리스트 (엑셀에 저장된 순서대로 추출)
patterns = df_dist['Pattern'].unique()

print("=== 상위 10개 패턴의 일자별 가장 많이 나온 등급 Top 3 및 비율 ===")

for pattern in patterns:
    print(f"\n★ 패턴: {pattern}")
    df_p = df_dist[df_dist['Pattern'] == pattern]
    
    for idx, row in df_p.iterrows():
        day = row['Day']
        # 등급별 비율만 추출하여 정렬
        ratios = {
            '1등급': row['1등급 Ratio (%)'],
            '2등급': row['2등급 Ratio (%)'],
            '3등급': row['3등급 Ratio (%)'],
            '4등급': row['4등급 Ratio (%)'],
            '5등급': row['5등급 Ratio (%)'],
            '6등급': row['6등급 Ratio (%)']
        }
        
        # 내림차순 정렬
        sorted_ratios = sorted(ratios.items(), key=lambda x: x[1], reverse=True)
        
        # 상위 3개 포맷팅
        top3_str = ", ".join([f"{grade} ({ratio:.1f}%)" for grade, ratio in sorted_ratios[:3]])
        print(f"  - {day}: {top3_str}")
