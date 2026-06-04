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
    cur = conn.cursor()
    cur.execute("SELECT * FROM company.master_company_list LIMIT 1")
    colnames = [desc[0] for desc in cur.description]
    print(f"Columns: {colnames}")
    cur.execute("SELECT COUNT(*) FROM company.master_company_list")
    print(f"Count: {cur.fetchone()[0]}")
    conn.close()
except Exception as e:
    print(f"Failed: {e}")
