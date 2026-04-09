import os
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

def run_test():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )
    
    target_date = '2026-03-17'
    filepath = r'C:\Users\Hubnet\antigravity\excel\수익률\종가매매2_수익률.txt'
    
    print(f"테스트 날짜: {target_date}")
    with open(filepath, 'r', encoding='utf-8') as f:
        query = f.read()
    
    # 원본 쿼리 실행 (3/17은 원래 범위에 포함됨)
    try:
        df = pd.read_sql_query(query, conn)
        df['일자'] = df['일자'].astype(str)
        df_filtered = df[df['일자'] == target_date]
        print(f"3/17 데이터 행 수: {len(df_filtered)}")
        if not df_filtered.empty:
            print(df_filtered.head())
    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_test()
