import os
import psycopg2

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
try:
    conn = psycopg2.connect(
        host=env.get('DB_HOST'), port=5432,
        dbname=env.get('DB_NAME'), user=env.get('DB_USER'), password=env.get('DB_PASSWORD')
    )
    with open('src/sql/backtest_sector_comparison_summary.sql', 'r', encoding='utf-8') as f:
        query = f.read()
    
    cur = conn.cursor()
    cur.execute(query)
    print("Success!")
    conn.close()
except Exception as e:
    print(f"Failed: {e}")
