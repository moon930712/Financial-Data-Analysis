import os, psycopg2, pandas as pd

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

def check_structure():
    conn = get_connection()
    tables = [
        ('visual', 'vsl_anly_stocks_price_subindex01'),
        ('visual', 'vsl_anly_stocks_price_subindex03'),
        ('company', 'krx_stocks_fundamental_info'),
        ('company', 'kis_kospi_info'),
        ('company', 'kis_kosdaq_info'),
        ('llm', 'naver_stock_report')
    ]
    
    for schema, table in tables:
        print(f"\n--- {schema}.{table} columns ---")
        q = f"SELECT column_name FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{table}'"
        cols = pd.read_sql_query(q, conn)
        print(cols['column_name'].tolist())
        
        # Check date range
        q_date = f"SELECT MIN(date), MAX(date) FROM {schema}.{table}"
        try:
            dates = pd.read_sql_query(q_date, conn)
            print(f"Date range: {dates.iloc[0,0]} ~ {dates.iloc[0,1]}")
        except:
            print("No date column or error")

    conn.close()

if __name__ == "__main__":
    check_structure()
