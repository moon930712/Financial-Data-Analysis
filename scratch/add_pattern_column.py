import pandas as pd
import os
import warnings

warnings.filterwarnings('ignore')

file_path = 'scratch/analyze_theme_cycle_with_prices_compact.xlsx'

print("엑셀 파일을 읽는 중입니다...")
# Load all sheets to preserve them
sheet_dict = pd.read_excel(file_path, sheet_name=None)
df_cycles = sheet_dict.get('Cycles(Summary)')
df_pivot = sheet_dict.get('Prices_Pivot_Compact')

if df_cycles is None or df_pivot is None:
    print("필요한 시트가 없습니다.")
    exit(1)

print("6 - N 패턴을 추출 중입니다...")
# 1. Extract pattern
patterns = []
for idx, row in df_cycles.iterrows():
    theme = row['테마명']
    if pd.isna(theme): continue
    
    start_date = str(row['6등급 날짜'])[:10]
    grades_str = row['등급변화 추이']
    if pd.isna(grades_str): continue
    
    grades_list = [g.strip() for g in str(grades_str).split('->')]
    first_jump = None
    for g in grades_list[1:]:
        if g != '6등급':
            first_jump = g
            break
            
    if first_jump:
        # first_jump is like '4등급'
        n = first_jump.replace('등급', '').strip()
        pattern_str = f"6 - {n}패턴"
        patterns.append({'테마명': theme, '시작일(Point A)': start_date, '6 -N패턴': pattern_str})

df_patterns = pd.DataFrame(patterns)

# 2. Merge into pivot
# Make sure format matches
df_pivot['시작일(Point A)'] = pd.to_datetime(df_pivot['시작일(Point A)']).dt.strftime('%Y-%m-%d')
df_pivot = df_pivot.merge(df_patterns, on=['테마명', '시작일(Point A)'], how='left')

# 3. Rearrange columns
cols = df_pivot.columns.tolist()
if '6 -N패턴' in cols:
    cols.remove('6 -N패턴')
    
if 'D+0' in cols:
    idx = cols.index('D+0')
    cols.insert(idx, '6 -N패턴')
else:
    cols.insert(3, '6 -N패턴')

df_pivot = df_pivot[cols]
sheet_dict['Prices_Pivot_Compact'] = df_pivot

# 4. Save back
print("엑셀 파일을 업데이트 중입니다...")
out_path = os.path.abspath(file_path)
with pd.ExcelWriter(out_path) as writer:
    for sheet_name, df in sheet_dict.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"완료! {out_path} 에 저장되었습니다.")
