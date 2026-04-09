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
    
    target_date = '2026-03-18'
    filepath = r'C:\Users\Hubnet\antigravity\excel\수익률\종가매매2_수익률.txt'
    
    print(f"테스트 파일 읽기: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        query = f.read()
    
    # 더 정확한 날짜 치환
    new_query = re.sub(r"'2026-03-10'", f"'{target_date}'", query)
    new_query = re.sub(r"'2026-03-17'", f"'{target_date}'", new_query)
    new_query = re.sub(r"'2026-04-08'", f"'{target_date}'", new_query)
    
    print("쿼리 실행 중 (이 단계에서 멈춘다면 DB 성능/용량 문제입니다)...")
    try:
        df = pd.read_sql_query(new_query, conn)
        print(f"추출 성공! 행 수: {len(df)}")
        print(df.head())
    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_test()
