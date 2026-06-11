import os
import psycopg2
import pandas as pd
import sys
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

def main():
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    with open('extract_target_patterns_with_rsi.sql', 'r', encoding='utf-8') as f:
        sql_template = f.read()

    # 2026년 1월 이후 영업일 조회
    df_dates = pd.read_sql("SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2026-01-01' ORDER BY date ASC", conn)
    valid_dates = pd.to_datetime(df_dates['date']).dt.strftime('%Y-%m-%d').tolist()

    print(f"Iterating over {len(valid_dates)} trading days...")
    all_results = []
    
    for i, dt in enumerate(valid_dates):
        if i % 10 == 0:
            print(f"Processing date {dt} ({i+1}/{len(valid_dates)})...")
            
        # SQL 구문의 변수를 현재 날짜로 치환
        sql = sql_template.replace("${date:sqlstring}", f"'{dt}'")
        try:
            df = pd.read_sql(sql, conn)
            if not df.empty:
                all_results.append(df)
        except Exception as e:
            print(f"Error executing on {dt}: {e}")

    if all_results:
        df_final = pd.concat(all_results, ignore_index=True)
        # 1. 추천종목만 필터링 (V3 조건 만족 종목)
        df_filtered = df_final[df_final['조건만족'] == '추천종목'].copy()
        df_filtered = df_filtered.sort_values(by=['Signal Date', 'Pattern', 'Theme', 'Stock Name'])
        
        if df_filtered.empty:
            print("조건을 만족하는 종목이 없습니다.")
            return

        # 2. 패턴별 Summary 생성
        # D+5 승률 계산: D+5 Return (%) > 0 인 경우 승리
        # 최고점 승률 계산: D+1 ~ D+5 중 하나라도 > 0 인 경우 승리
        returns_cols = ['D+1 Return (%)', 'D+2 Return (%)', 'D+3 Return (%)', 'D+4 Return (%)', 'D+5 Return (%)']
        
        df_filtered['Win_D5'] = df_filtered['D+5 Return (%)'] > 0
        df_filtered['Win_Any'] = df_filtered[returns_cols].max(axis=1) > 0
        
        summary = df_filtered.groupby('Pattern').agg(
            Total_Count=('Stock Name', 'count'),
            Win_Count_D5=('Win_D5', 'sum'),
            Win_Count_AnyDay=('Win_Any', 'sum'),
            Avg_D5_Return=('D+5 Return (%)', 'mean')
        ).reset_index()
        
        summary['D+5 종가 승률 (%)'] = round((summary['Win_Count_D5'] / summary['Total_Count']) * 100, 2)
        summary['5일 내 고점 승률 (%)'] = round((summary['Win_Count_AnyDay'] / summary['Total_Count']) * 100, 2)
        summary['평균 D+5 수익률 (%)'] = summary['Avg_D5_Return'].astype(float).round(2)
        
        summary = summary[['Pattern', 'Total_Count', 'D+5 종가 승률 (%)', '5일 내 고점 승률 (%)', '평균 D+5 수익률 (%)']]
        summary.columns = ['테마 패턴', '검색된 종목 수', 'D+5 종가 승률 (%)', '5일 내 고점 승률 (%)', '평균 D+5 수익률 (%)']
        
        sort_order = {
            '6등급 -> 4등급 -> 1등급': 1, 
            '4등급 -> 3등급 -> 1등급': 2, 
            '4등급 -> 2등급 -> 2등급': 3,
            '3등급 -> 2등급 -> 1등급': 4,
            '3등급 -> 3등급 -> 1등급': 5
        }
        summary['sort_key'] = summary['테마 패턴'].map(sort_order).fillna(99)
        summary = summary.sort_values('sort_key').drop(columns=['sort_key'])

        # 계산용 임시 컬럼 삭제
        df_filtered = df_filtered.drop(columns=['Win_D5', 'Win_Any'])
        
        # 3. 엑셀 저장
        out_path = 'backtest_extract_target_patterns_with_rsi_features.xlsx'
        with pd.ExcelWriter(out_path) as writer:
            df_filtered.to_excel(writer, sheet_name='Raw Data', index=False)
            summary.to_excel(writer, sheet_name='Summary', index=False)
            
        print(f"\nSaved {len(df_filtered)} filtered rows to {out_path} with Summary sheet.")
        print("\n=== Pattern Summary ===")
        print(summary.to_string(index=False))
    else:
        print("No results found.")
        
    conn.close()

if __name__ == '__main__':
    main()
