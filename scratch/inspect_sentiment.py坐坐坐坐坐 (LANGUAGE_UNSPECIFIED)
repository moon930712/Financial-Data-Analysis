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

def inspect_sentiment_table():
    conn = get_connection()
    # 1. Get column names and types
    query_schema = """
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'visual' 
      AND table_name = 'vsl_anly_stocks_price_subindex03'
    ORDER BY ordinal_position;
    """
    schema = pd.read_sql_query(query_schema, conn)
    print("=== Table Schema ===")
    print(schema)
    
    # 2. Get sample data
    query_sample = "SELECT * FROM visual.vsl_anly_stocks_price_subindex03 LIMIT 5;"
    sample = pd.read_sql_query(query_sample, conn)
    print("\n=== Sample Data ===")
    print(sample)
    
    conn.close()

if __name__ == "__main__":
    inspect_sentiment_table()
