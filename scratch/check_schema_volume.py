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
    query = "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'visual' AND table_name = 'vsl_anly_stocks_price_subindex01'"
    df = pd.read_sql_query(query, conn)
    print("Columns in visual.vsl_anly_stocks_price_subindex01:")
    print(df)
    
    # Also find any columns related to volume/amount
    query2 = "SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE column_name LIKE '%amt%' OR column_name LIKE '%trd%' OR column_name LIKE '%vol%' OR column_name LIKE '%대금%' OR column_name LIKE '%거래%';"
    df2 = pd.read_sql_query(query2, conn)
    print("\nColumns potentially related to trading amount/volume:")
    print(df2[df2['table_schema'].isin(['public', 'visual', 'company', 'company_master'])])
finally:
    conn.close()
