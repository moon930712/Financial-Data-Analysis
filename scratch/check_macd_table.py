import psycopg2, os
import pandas as pd

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

print("Schema for visual.vsl_anly_stocks_price_subindex02:")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'visual' AND table_name = 'vsl_anly_stocks_price_subindex02'")
for row in cur.fetchall():
    print(row)

print("\nSample data from visual.vsl_anly_stocks_price_subindex02 (latest date):")
cur.execute("SELECT * FROM visual.vsl_anly_stocks_price_subindex02 WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02) LIMIT 5")
for row in cur.fetchall():
    print(row)

conn.close()
