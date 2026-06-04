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
df = pd.read_sql_query("SELECT * FROM company.financial_factor_quarterly LIMIT 5", conn)
print(df.columns.tolist())
print(df.head())
conn.close()
