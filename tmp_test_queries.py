import os
import psycopg2
import pandas as pd

def load_env():
    with open('c:/Users/Hubnet/antigravity/.env', 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env()
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

def test_sql(filepath):
    try:
        print(f"\n--- Testing {os.path.basename(filepath)} ---")
        with open(filepath, 'r', encoding='utf-8') as f:
            query = f.read()
        df = pd.read_sql_query(query, conn)
        print(f"SUCCESS! Row count: {len(df)}")
        if len(df) > 0:
            print(df.head(3))
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

try:
    test_sql('c:/Users/Hubnet/antigravity/src/sql/industry_zscore_ranking.sql')
    test_sql('c:/Users/Hubnet/antigravity/src/sql/stock_turnaround_ranking.sql')
finally:
    conn.close()
