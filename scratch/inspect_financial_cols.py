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
for table in ['financial_base_quarterly', 'financial_factor_quarterly']:
    print(f"--- Columns in {table} ---")
    cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
    for col in cur.fetchall():
        print(f"{col[0]}: {col[1]}")
    print("\n")
conn.close()
