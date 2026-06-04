import os
import psycopg2
import pandas as pd

def load_env(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

def get_connection():
    load_env('.env')
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def test_query():
    conn = get_connection()
    try:
        # Use absolute path for SQL file too
        sql_path = r'c:\Users\Hubnet\antigravity\src\sql\stock_phase_master.sql'
        with open(sql_path, 'r', encoding='utf-8') as f:
            query = f.read()
            # Replace Grafana variables
            query = query.replace('${wics_name2:sqlstring}', "'All'")
        
        df = pd.read_sql_query(query, conn)
        print("\n[ 상위 20개 섹터 랭킹 (Master Score 적용) ]")
        # Unicode encoding for terminal
        print(df.head(20).to_string(index=False))
        
        # 보험 업종 확인
        insurance_df = df[df['중분류명'] == '보험']
        if not insurance_df.empty:
            print("\n[ 보험 업종 상세 ]")
            print(insurance_df.to_string(index=False))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_query()
