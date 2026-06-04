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
    # 1. Check industry.theme_name_list columns
    query1 = "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'industry' AND table_name = 'theme_name_list'"
    df1 = pd.read_sql_query(query1, conn)
    print("Columns in industry.theme_name_list:")
    print(df1)
    
    # 2. Test query to join and calculate
    # Let's assume industry.theme_name_list has 'theme_name' and 'stock_code' based on previous context, but I'll see the schema first.
    # We will just print the schema for now.
finally:
    conn.close()
