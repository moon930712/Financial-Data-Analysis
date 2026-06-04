import psycopg2
import os

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

def inspect_schema():
    conn = get_connection()
    cur = conn.cursor()
    
    print("--- Tables in 'company' schema ---")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'company'")
    for table in cur.fetchall():
        print(table[0])
        
    print("\n--- Columns in 'company.kis_kospi_info' ---")
    try:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'kis_kospi_info'")
        for col in cur.fetchall():
            print(f"{col[0]}: {col[1]}")
    except:
        print("Table 'kis_kospi_info' not found or inaccessible.")

    print("\n--- Columns in 'company.krx_stocks_fundamental_info' ---")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'krx_stocks_fundamental_info'")
    for col in cur.fetchall():
        print(f"{col[0]}: {col[1]}")

    conn.close()

if __name__ == "__main__":
    inspect_schema()
