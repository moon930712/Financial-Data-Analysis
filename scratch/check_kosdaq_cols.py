import psycopg2, os
def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
load_env()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432), dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'))
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'company' AND table_name = 'kis_kosdaq_info'")
cols = [c[0] for c in cur.fetchall()]
print("KOSDAQ Columns:", [c for c in cols if 'market' in c.lower()])
conn.close()
