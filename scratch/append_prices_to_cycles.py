import pandas as pd
import psycopg2
import sys
import os
import warnings

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

def load_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env_vars[k] = v
    except: pass
    return env_vars

env = load_env()
conn = psycopg2.connect(
    host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
    dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
)

file_path = 'scratch/analyze_theme_cycle_6_1_6.xlsx'
df_cycles = pd.read_excel(file_path, sheet_name='Cycles')
df_cycles = df_cycles.dropna(subset=['테마명'])

price_records = []

print("DB에서 종가 데이터를 추출합니다...")

for idx, row in df_cycles.iterrows():
    theme = row['테마명']
    start_date = row['6등급 날짜']
    end_date = row['6등급날짜']
    
    query = """
    SELECT nt.theme_name, nt.stock_name, v.date, v.close
    FROM industry.theme_name_list nt
    JOIN visual.vsl_anly_stocks_price_subindex01 v ON nt.stock_code = v.stock_code
    WHERE nt.theme_name = %s AND v.date >= %s AND v.date <= %s
    ORDER BY nt.stock_name, v.date
    """
    
    df_prices = pd.read_sql(query, conn, params=(theme, start_date, end_date))
    
    if not df_prices.empty:
        # 고유한 날짜를 오름차순으로 정렬하여 D+0, D+1 등급 인덱스 부여 (빈칸 최소화)
        unique_dates = df_prices['date'].drop_duplicates().sort_values().tolist()
        date_to_day = {d: f"D+{i}" for i, d in enumerate(unique_dates)}
        df_prices['진행일차'] = df_prices['date'].map(date_to_day)
        
        # 시작일자 컨텍스트를 위해 추가
        df_prices['시작일(Point A)'] = start_date
        
        price_records.append(df_prices)

if price_records:
    df_all_prices = pd.concat(price_records, ignore_index=True)
    df_all_prices['date'] = pd.to_datetime(df_all_prices['date']).dt.strftime('%Y-%m-%d')
    df_all_prices.rename(columns={'theme_name': '테마명', 'stock_name': '종목명', 'date': '날짜', 'close': '종가'}, inplace=True)
    
    print("엑셀 파일에 시트를 추가하여 저장합니다...")
    out_path = os.path.abspath('scratch/analyze_theme_cycle_with_prices_compact.xlsx')
    
    with pd.ExcelWriter(out_path) as writer:
        df_cycles.to_excel(writer, sheet_name='Cycles(Summary)', index=False)
        
        # 피벗 테이블 생성: 날짜 대신 D+0, D+1... 형식으로 정렬
        try:
            df_pivot = df_all_prices.pivot(index=['테마명', '종목명', '시작일(Point A)'], columns='진행일차', values='종가').reset_index()
            
            # D+ 컬럼 정렬
            cols = df_pivot.columns.tolist()
            base_cols = ['테마명', '종목명', '시작일(Point A)']
            d_cols = [c for c in cols if str(c).startswith('D+')]
            d_cols.sort(key=lambda x: int(x.split('+')[1]))
            
            df_pivot = df_pivot[base_cols + d_cols]
            df_pivot.to_excel(writer, sheet_name='Prices_Pivot_Compact', index=False)
        except Exception as e:
            print("Pivot Error:", e)
            
        # 세로(Long) 포맷 원본 데이터도 저장
        df_all_prices.to_excel(writer, sheet_name='Prices_Raw_Data', index=False)

    print(f"\\n완료! 결과가 {out_path} 에 저장되었습니다.")
else:
    print("추출할 데이터가 없습니다.")

conn.close()
