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

try:
    query = """
    SELECT table_schema, table_name, column_name 
    FROM information_schema.columns 
    WHERE column_name IN ('acml_vol', 'stck_clpr') AND table_schema = 'company'
    """
    df = pd.read_sql_query(query, conn)
    print("Tables with volume/price columns:")
    print(df)
    
finally:
    conn.close()
