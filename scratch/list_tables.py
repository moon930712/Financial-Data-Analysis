import os
import psycopg2
import pandas as pd

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    try:
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip()
                    except: pass

load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def list_tables():
    conn = get_connection()
    q = "SELECT table_name FROM information_schema.tables WHERE table_schema IN ('company', 'visual', 'llm') ORDER BY table_schema;"
    df = pd.read_sql_query(q, conn)
    print(df)
    conn.close()

if __name__ == "__main__":
    list_tables()
