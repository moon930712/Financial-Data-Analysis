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

print("Schema for company.naver_theme:")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'company' AND table_name = 'naver_theme'")
for row in cur.fetchall():
    print(row)

print("\nSample data from company.naver_theme:")
cur.execute("SELECT * FROM company.naver_theme LIMIT 5")
for row in cur.fetchall():
    print(row)

conn.close()
