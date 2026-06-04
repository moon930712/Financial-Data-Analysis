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

print("Columns of company.krx_stocks_investor_shares_trading_info:")
cols_query = """
SELECT column_name 
FROM information_schema.columns 
WHERE table_schema = 'company' 
  AND table_name = 'krx_stocks_investor_shares_trading_info'
"""
print(pd.read_sql_query(cols_query, conn))

print("\nDistinct investor types:")
investor_query = "SELECT DISTINCT investor FROM company.krx_stocks_investor_shares_trading_info"
print(pd.read_sql_query(investor_query, conn))

print("\nSample data from the table:")
sample_query = "SELECT * FROM company.krx_stocks_investor_shares_trading_info LIMIT 5"
print(pd.read_sql_query(sample_query, conn))

conn.close()
