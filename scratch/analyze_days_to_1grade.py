import pandas as pd
import numpy as np
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 데이터 로드
df = pd.read_excel('scratch/analyze_sector_grade_trend_ac.xlsx', sheet_name='Raw Data (Per Stock)')

days_to_1grade = []

for trend_str in df['등급변화추이'].dropna():
    grades = [g.strip() for g in trend_str.split('->')]
    
    if '1등급' in grades:
        # 1등급의 첫 등장 인덱스를 찾습니다. (인덱스 0이 Point A 당일이므로, 인덱스 값 자체가 소요 일수가 됩니다)
        first_idx = grades.index('1등급')
        days_to_1grade.append(first_idx)

if not days_to_1grade:
    print("6등급에서 1등급으로 도달한 케이스가 없습니다.")
else:
    days_to_1grade = np.array(days_to_1grade)
    
    print(f"=== 6등급에서 1등급 도달 소요 일수 (영업일 기준) ===")
    print(f"총 도달 케이스: {len(days_to_1grade)}회")
    print(f"평균 소요 일수: {np.mean(days_to_1grade):.1f}일")
    print(f"중앙값(Median): {np.median(days_to_1grade):.1f}일")
    print(f"최소 소요 일수: {np.min(days_to_1grade)}일 (다음 날 바로 도달)")
    print(f"최대 소요 일수: {np.max(days_to_1grade)}일")
    
    print("\n[소요 일수 분포]")
    bins = [0, 1, 3, 5, 10, 20, 1000]
    labels = ['1일 (다음날)', '2~3일', '4~5일', '6~10일', '11~20일', '21일 이상']
    
    hist, _ = np.histogram(days_to_1grade, bins=bins)
    
    for label, count in zip(labels, hist):
        pct = count / len(days_to_1grade) * 100
        print(f"{label:12s}: {count:4d}회 ({pct:5.1f}%)")
