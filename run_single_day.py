import os
import glob
import psycopg2
import pandas as pd
import re
import warnings
warnings.filterwarnings('ignore')

def load_env():
    with open(r'c:\Users\Hubnet\antigravity\.env', 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line:
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

# 목표 날짜
target_date = '2026-03-18'

profit_dir = r'C:\Users\Hubnet\antigravity\excel\수익률'
stock_dir = r'C:\Users\Hubnet\antigravity\excel\종목'

summary_dfs = []
detail_dfs = []

def process_queries(directory, strategy_suffix, df_list, sheet_type):
    if not os.path.exists(directory):
        return

    for filepath in glob.glob(os.path.join(directory, '*.txt')):
        filename = os.path.basename(filepath)
        strategy_name = filename.replace(strategy_suffix, '').replace('.txt', '')
        print(f"[{sheet_type}] {strategy_name} 실행 중...")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                query = f.read()
            
            # SQL 내의 BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD' 패턴을 찾아 target_date로 변경
            # 여러 형태의 따옴표나 공백 대응
            pattern = r"BETWEEN\s+['\"](\d{4}-\d{2}-\d{2})['\"]\s+AND\s+['\"](\d{4}-\d{2}-\d{2})['\"]"
            optimized_query = re.sub(pattern, f"BETWEEN '{target_date}' AND '{target_date}'", query, flags=re.IGNORECASE)
            
            # 일부 쿼리는 date = '...' 형태일 수도 있음
            # optimized_query = re.sub(r"date\s*=\s*['\"](\d{4}-\d{2}-\d{2})['\"]", f"date = '{target_date}'", optimized_query)

            df = pd.read_sql_query(optimized_query, conn)
            
            date_col = next((c for c in df.columns if c in ['일자', 'date', '추천일자', 'stck_bsop_date', '기간']), None)
            
            if date_col:
                df[date_col] = df[date_col].astype(str).str[:10]
                df_filtered = df[df[date_col] == target_date].copy()
                
                if not df_filtered.empty:
                    df_filtered.insert(0, '전략명', strategy_name)
                    df_list.append(df_filtered)
                    print(f"  -> 성공: {len(df_filtered)}건 추출")
                else:
                    print(f"  -> {target_date} 데이터가 결과에 없음 (필터링됨)")
            else:
                print(f"  -> 날짜 컬럼을 찾을 수 없음")
                
        except Exception as e:
            print(f"  -> 에러 발생: {str(e)[:100]}...")

print(f"=== {target_date} 추출 시작 (쿼리 내 날짜 범위 자동 보정) ===")
process_queries(profit_dir, '_수익률', summary_dfs, "수익률")
process_queries(stock_dir, '_종목', detail_dfs, "종목")

conn.close()

if not summary_dfs and not detail_dfs:
    print("\n[알림] 추출된 데이터가 전혀 없습니다. 쿼리 조건을 확인해 주세요.")
else:
    output_excel = r'C:\Users\Hubnet\antigravity\excel\Target_Result_20260318.xlsx'
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        if summary_dfs:
            pd.concat(summary_dfs, ignore_index=True).to_excel(writer, sheet_name='시트1(수익률)', index=False)
        if detail_dfs:
            pd.concat(detail_dfs, ignore_index=True).to_excel(writer, sheet_name='시트2(종목)', index=False)
    print(f"\n[완료] 엑셀 생성이 끝났습니다: {output_excel}")
