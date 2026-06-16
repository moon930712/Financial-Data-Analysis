import pandas as pd
from collections import defaultdict
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 데이터 로드
df = pd.read_excel('scratch/analyze_theme_cycle_6_1_6.xlsx', sheet_name='Cycles')

transitions_1 = defaultdict(int) # 6 -> X (일간)
state_trans_1 = defaultdict(int) # 6 -> X (상태 변화)

for trend_str in df['등급변화 추이'].dropna():
    grades = [g.strip() for g in trend_str.split('->')]
    
    # 1. 일간 변화 (매일매일의 변화)
    for i in range(len(grades) - 1):
        if grades[i] == '6등급':
            next_g = grades[i+1]
            transitions_1[next_g] += 1

    # 2. 상태 변화 (연속된 중복 등급 제거)
    compressed = []
    for g in grades:
        if not compressed or compressed[-1] != g:
            compressed.append(g)
            
    for i in range(len(compressed) - 1):
        if compressed[i] == '6등급':
            next_g = compressed[i+1]
            state_trans_1[next_g] += 1

print("=== [방식 1: 일간 변화] 6등급 다음 날의 등급 비율 ===")
total_1 = sum(transitions_1.values())
if total_1 > 0:
    for k in sorted(transitions_1.keys(), reverse=True):
        v = transitions_1[k]
        print(f"6등급 -> {k}: {v}회 ({v/total_1*100:.1f}%)")

print("\n" + "="*50 + "\n")

print("=== [방식 2: 실질적 상태 변화] 6등급에서 '다른 등급'으로 바뀔 때의 비율 (6->6 무시) ===")
total_s1 = sum(state_trans_1.values())
if total_s1 > 0:
    for k in sorted(state_trans_1.keys(), reverse=True):
        v = state_trans_1[k]
        print(f"6등급 -> {k}: {v}회 ({v/total_s1*100:.1f}%)")
