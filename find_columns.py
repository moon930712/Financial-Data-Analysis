import os
import psycopg2
import pandas as pd

def load_env(filepath):
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('.env')

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

query = """
SELECT column_name
FROM information_schema.columns 
WHERE table_schema = 'company' AND table_name = 'krx_stocks_fundamental_info'
"""

try:
    df = pd.read_sql_query(query, conn)
    print(df['column_name'].tolist())
finally:
    conn.close()

