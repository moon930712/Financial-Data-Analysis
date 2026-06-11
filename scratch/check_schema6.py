import psycopg2, os
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
    host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
    dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
)
cur = conn.cursor()
cur.execute("SELECT * FROM industry.theme_name_list LIMIT 1")
print('theme_name_list:', cur.fetchone())
cur.execute("SELECT * FROM company.naver_theme LIMIT 1")
print('naver_theme:', cur.fetchone())
conn.close()
