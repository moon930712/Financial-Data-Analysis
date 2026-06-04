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
conn = psycopg2.connect(
    host=env.get('DB_HOST'), port=5432,
    dbname=env.get('DB_NAME'), user=env.get('DB_USER'), password=env.get('DB_PASSWORD')
)
try:
    cur = conn.cursor()
    for table in ['visual.vsl_anly_stocks_price_subindex01', 'visual.vsl_anly_stocks_price_subindex02', 'visual.vsl_krx_stocks_cap']:
        cur.execute(f'SELECT MIN(date), MAX(date) FROM {table}')
        res = cur.fetchone()
        print(f"{table}: {res}")
finally:
    conn.close()
