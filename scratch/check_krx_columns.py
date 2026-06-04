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
    query = "SELECT column_name FROM information_schema.columns WHERE table_schema = 'company' AND table_name = 'krx_stocks_fundamental_info' ORDER BY ordinal_position;"
    df = pd.read_sql_query(query, conn)
    print(df['column_name'].tolist())
    conn.close()

if __name__ == "__main__":
    check_columns()
