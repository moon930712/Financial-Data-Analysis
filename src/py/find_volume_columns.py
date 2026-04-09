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
SELECT 
    c.table_schema, 
    c.table_name, 
    c.column_name, 
    col_description(pc.oid, c.ordinal_position) AS column_comment
FROM information_schema.columns c
JOIN pg_class pc ON pc.relname = c.table_name
JOIN pg_namespace pn ON pn.oid = pc.relnamespace AND pn.nspname = c.table_schema
WHERE lower(c.column_name) LIKE '%volume%'
   OR lower(c.column_name) LIKE '%acml_tr_pbmn%'
   OR c.column_name LIKE '%vol%'
   OR lower(col_description(pc.oid, c.ordinal_position)) LIKE '%거래량%'
"""

try:
    df = pd.read_sql_query(query, conn)
    pd.set_option('display.max_rows', None)
    print(df[df['table_schema'].isin(['public', 'company', 'market', 'fin_prod'])])
finally:
    conn.close()
