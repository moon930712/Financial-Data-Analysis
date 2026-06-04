import psycopg2, os
import pandas as pd
import sys, io

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST')
        , port=os.environ.get('DB_PORT', 5432)
        , dbname=os.environ.get('DB_NAME')
        , user=os.environ.get('DB_USER')
        , password=os.environ.get('DB_PASSWORD')
    )

with open('src/sql/stock_phase_master.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

try:
    conn = get_connection()
    # 그라파나용 주석 필터 처리 (특정 테마 하나만 테스트)
    # 주석 해제 및 변수 하드코딩
    test_sql = sql.replace("--  AND theme_name IN ($industry_phase)", "AND theme_name = '도시가스'")
    df = pd.read_sql(test_sql, conn)
    print("\n" + "="*80)
    print("### [도시가스 테마 개별종목 국면 상세 리스트] ###")
    print("="*80)
    if not df.empty:
        print(df.to_string(index=False))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
