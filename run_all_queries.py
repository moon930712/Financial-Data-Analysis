import os
import glob
import psycopg2
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

def load_env():
    with open(r'c:\Users\Hubnet\antigravity\.env', 'r') as f:
        for line in f:
            line = line.strip()
            if '= ' in line or '=' in line:
                try:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
                except: pass

load_env()

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

start_date = '2026-03-10'
end_date = '2026-03-18'

profit_dir = r'C:\Users\Hubnet\antigravity\excel\수익률'
stock_dir = r'C:\Users\Hubnet\antigravity\excel\종목'

summary_dfs = []
detail_dfs = []

print("=== 수익률 (시트1) 데이터 수집 시작 ===")
if os.path.exists(profit_dir):
    for filepath in glob.glob(os.path.join(profit_dir, '*.txt')):
        filename = os.path.basename(filepath)
        strategy_name = filename.replace('_수익률.txt', '').replace('.txt', '')
        print(f"Running: {filename}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                query = f.read()
            df = pd.read_sql_query(query, conn)
            
            date_col = next((c for c in df.columns if c in ['일자', 'date', '추천일자']), None)
            if date_col:
                df[date_col] = df[date_col].astype(str).str[:10]
                # 기간 필터링: 03-10 ~ 03-18
                df = df[(df[date_col] >= start_date) & (df[date_col] <= end_date)].copy()
                if not df.empty:
                    df.insert(0, '전략명', strategy_name) # 전략명 최전방 배치
                    summary_dfs.append(df)
        except Exception as e:
            print(f"Error in {filename}: {e}")

print("=== 종목 (시트2) 데이터 수집 시작 ===")
if os.path.exists(stock_dir):
    for filepath in glob.glob(os.path.join(stock_dir, '*.txt')):
        filename = os.path.basename(filepath)
        strategy_name = filename.replace('_종목.txt', '').replace('.txt', '')
        print(f"Running: {filename}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                query = f.read()
            df = pd.read_sql_query(query, conn)
            
            date_col = next((c for c in df.columns if c in ['일자', 'date', '추천일자', 'stck_bsop_date']), None)
            if date_col:
                df[date_col] = df[date_col].astype(str).str[:10]
                # 기간 필터링: 03-10 ~ 03-18
                df = df[(df[date_col] >= start_date) & (df[date_col] <= end_date)].copy()
                if not df.empty:
                    df.insert(0, '전략명', strategy_name)
                    detail_dfs.append(df)
        except Exception as e:
            print(f"Error in {filename}: {e}")

conn.close()

output_excel = r'C:\Users\Hubnet\antigravity\excel\Combined_Strategies_20260310_20260318.xlsx'

print(f"\n데이터 결합 및 엑셀 저장 준비...")
with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
    if summary_dfs:
        df_final_summary = pd.concat(summary_dfs, ignore_index=True)
        date_col_idx = [c for c in df_final_summary.columns if c in ['일자', 'date', '추천일자']]
        if date_col_idx:
            df_final_summary = df_final_summary.sort_values(by=date_col_idx[0])
        df_final_summary.to_excel(writer, sheet_name='시트1(수익률)', index=False)
        print(f"시트1(수익률) 저장 완료: {len(df_final_summary)}행")
    else:
        pd.DataFrame({'Message': ['수익률 데이터 없음']}).to_excel(writer, sheet_name='시트1(수익률)', index=False)
        
    if detail_dfs:
        df_final_detail = pd.concat(detail_dfs, ignore_index=True)
        date_col_idx = [c for c in df_final_detail.columns if c in ['일자', 'date', '추천일자', 'stck_bsop_date']]
        if date_col_idx:
            df_final_detail = df_final_detail.sort_values(by=date_col_idx[0])
        df_final_detail.to_excel(writer, sheet_name='시트2(종목)', index=False)
        print(f"시트2(종목) 저장 완료: {len(df_final_detail)}행")
    else:
        pd.DataFrame({'Message': ['종목 데이터 없음']}).to_excel(writer, sheet_name='시트2(종목)', index=False)

print(f"\n엑셀 저장 성공! 저장 위치: {output_excel}")
