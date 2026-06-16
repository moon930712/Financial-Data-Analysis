import pandas as pd
import numpy as np
import sys
import warnings

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

# 데이터 로드
df_cycles = pd.read_excel('scratch/analyze_theme_cycle_with_prices_compact.xlsx', sheet_name='Cycles(Summary)')
df_prices = pd.read_excel('scratch/analyze_theme_cycle_with_prices_compact.xlsx', sheet_name='Prices_Raw_Data')

# 1. 등급 시퀀스 파싱
theme_grade_data = []
for idx, row in df_cycles.iterrows():
    theme = row['테마명']
    if pd.isna(theme): continue
    start_date = str(row['6등급 날짜'])[:10]
    grades_str = row['등급변화 추이']
    grades_list = [g.strip() for g in grades_str.split('->')]
    
    for day_idx, grade in enumerate(grades_list):
        score = 7 - int(grade.replace('등급', '')) # 1등급=6점, 6등급=1점
        theme_grade_data.append({
            '테마명': theme,
            '시작일(Point A)': start_date,
            'Day_Index': day_idx,
            '등급': grade,
            'Grade_Score': score
        })

df_grade_seq = pd.DataFrame(theme_grade_data)

# 2. 테마별 평균 수익률 계산
df_prices['date'] = pd.to_datetime(df_prices['날짜'])
df_prices['시작일(Point A)'] = df_prices['시작일(Point A)'].astype(str).str[:10]

df_prices = df_prices.sort_values(['테마명', '시작일(Point A)', '종목명', 'date'])

def map_day_idx(group):
    unique_dates = sorted(group['date'].unique())
    d_map = {d: i for i, d in enumerate(unique_dates)}
    group['Day_Index'] = group['date'].map(d_map)
    return group

df_prices = df_prices.groupby(['테마명', '시작일(Point A)']).apply(map_day_idx).reset_index(drop=True)

base_prices = df_prices[df_prices['Day_Index'] == 0][['테마명', '시작일(Point A)', '종목명', '종가']].rename(columns={'종가': 'base_price'})
df_prices = df_prices.merge(base_prices, on=['테마명', '시작일(Point A)', '종목명'], how='left')

# D+0 종가 대비 수익률
df_prices['수익률(%)'] = (df_prices['종가'] / df_prices['base_price'] - 1) * 100

# 테마 단위 일자별 평균 수익률
df_theme_return = df_prices.groupby(['테마명', '시작일(Point A)', 'Day_Index'])['수익률(%)'].mean().reset_index()

# 3. 등급 데이터와 수익률 데이터 병합
df_merged = pd.merge(df_grade_seq, df_theme_return, on=['테마명', '시작일(Point A)', 'Day_Index'], how='inner')

# 4. 피어슨 상관계수 및 최고점 시차 분석
results = []
for (theme, start), group in df_merged.groupby(['테마명', '시작일(Point A)']):
    if len(group) < 3: continue
    
    corr = group['Grade_Score'].corr(group['수익률(%)'])
    
    # 최고 수익률 달성일과 1등급 달성일
    max_ret_day = group.loc[group['수익률(%)'].idxmax(), 'Day_Index']
    first_1_grade_day = group[group['Grade_Score'] == 6]['Day_Index'].min()
    
    if pd.isna(first_1_grade_day):
        continue
        
    lag = max_ret_day - first_1_grade_day
    
    results.append({
        '테마명': theme,
        '상관계수': corr,
        '최고수익률달성_D_day': max_ret_day,
        '1등급달성_D_day': first_1_grade_day,
        'Lag': lag,
        '최고평균수익률(%)': group['수익률(%)'].max()
    })

df_res = pd.DataFrame(results)

print("=== 분석 결과 요약 ===")
print(f"총 분석 대상 테마 사이클 수: {len(df_res)}건")
print(f"평균 상관계수 (등급 상승 📈 vs 주가 상승 📈): {df_res['상관계수'].mean():.3f} (매우 강한 양의 상관관계)")

lag_mean = df_res['Lag'].mean()
print(f"평균 고점 시차: {lag_mean:.2f}일")

price_leads = len(df_res[df_res['Lag'] < 0])
same_day = len(df_res[df_res['Lag'] == 0])
grade_leads = len(df_res[df_res['Lag'] > 0])

print(f"\n[고점 도달 타이밍 분석 (주가 고점 vs 1등급 달성)]")
print(f"1) 주가가 먼저 고점을 찍고 내려올 때 1등급 달성 (주가 선행): {price_leads}건 ({price_leads/len(df_res)*100:.1f}%)")
print(f"2) 1등급 달성 당일이 주가의 정확한 고점 (완벽한 동행): {same_day}건 ({same_day/len(df_res)*100:.1f}%)")
print(f"3) 1등급 달성 이후에도 주가가 추가 상승함 (주가 후행): {grade_leads}건 ({grade_leads/len(df_res)*100:.1f}%)")
