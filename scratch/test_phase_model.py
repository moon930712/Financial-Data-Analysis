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

with open('src/sql/industry_phase_master.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

try:
    conn = get_connection()
    # 주석 해제된 SQL을 실행하여 상세 열도 함께 로드해 디버깅 테스트
    test_sql = sql.replace("/*", "").replace("*/", "")
    df = pd.read_sql(test_sql, conn)
    print("\n" + "="*80)
    print("### [생애주기 국면 비율(%) 기반 테마 순위] ###")
    print("="*80)
    if not df.empty:
        print(df.head(20).to_string(index=False))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
