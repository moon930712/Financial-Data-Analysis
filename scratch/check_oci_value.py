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

cur.execute("SELECT shortcode, koreanname, marketcap FROM company.kis_kospi_info WHERE shortcode = '010060'")
print("OCI Data:", cur.fetchall())

conn.close()
