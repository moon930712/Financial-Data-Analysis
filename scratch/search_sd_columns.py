import os
import psycopg2
import pandas as pd

# Load .env
if os.path.exists('.env'):
    for line in open('.env'):
        if '=' in line:
            k, v = line.strip().split('=', 1)
            os.environ.setdefault(k, v)

# Connect to DB
conn = psycopg2.connect(
    host=os.environ['DB_HOST'],
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ['DB_NAME'],
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD']
)

# Search for columns related to supply/demand in all tables
keywords = ['frgn', 'orgn', 'indiv', 'inst', '개인', '외국인', '기관', 'invst', 'buy', 'sell']

query = """
SELECT table_schema, table_name, column_name
FROM information_schema.columns
WHERE table_schema IN ('visual', 'company')
  AND (
    column_name ~* 'frgn|orgn|indiv|inst|invst|buy|sell'
  )
ORDER BY table_schema, table_name, column_name
"""

df = pd.read_sql_query(query, conn)
print("Found potential supply/demand columns:")
print(df.to_string())

# Also search for tables that might be relevant
table_query = """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('visual', 'company')
  AND (
    table_name ~* 'investor|supply|demand|trading|buy|sell'
  )
"""
df_tables = pd.read_sql_query(table_query, conn)
print("\nFound potential supply/demand tables:")
print(df_tables.to_string())

conn.close()
