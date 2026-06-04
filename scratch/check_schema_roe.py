import os
import psycopg2
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
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def check_columns():
    conn = get_connection()
    tables = [
        ('company', 'krx_stocks_fundamental_info'),
        ('company', 'kis_kospi_info'),
        ('company', 'kis_kosdaq_info')
    ]
    for schema, table in tables:
        query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{table}';"
        df = pd.read_sql_query(query, conn)
        print(f"\n--- {schema}.{table} ---")
        print(df)
    conn.close()

if __name__ == "__main__":
    check_columns()
