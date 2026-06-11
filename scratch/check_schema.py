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
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema IN ('industry', 'visual') AND table_name LIKE '%judal%'")
print('Judal Tables:', cur.fetchall())
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema IN ('industry', 'visual') AND table_name LIKE '%theme%'")
print('Theme Tables:', cur.fetchall())
conn.close()
