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
def get_connection():
    return psycopg2.connect(host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432), dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'))
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM visual.vsl_anly_stocks_price_subindex01")
print('Price Count:', cur.fetchone())
cur.execute("SELECT COUNT(*) FROM company.krx_stocks_fundamental_info")
print('PBR Count:', cur.fetchone())
conn.close()
