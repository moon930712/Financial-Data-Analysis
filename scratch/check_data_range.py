import os
import psycopg2

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

load_env()

def check_range():
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            port=os.environ.get('DB_PORT', 5432),
            dbname=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD')
        )
        cur = conn.cursor()
        
        print("--- Checking Table: company.krx_stocks_fundamental_info ---")
        cur.execute('SELECT MIN(date), MAX(date), COUNT(*) FROM company.krx_stocks_fundamental_info')
        res = cur.fetchone()
        print(f"Range: {res[0]} ~ {res[1]} (Count: {res[2]})")
        
        print("\n--- Checking Table: visual.vsl_anly_stocks_price_subindex01 ---")
        cur.execute('SELECT MIN(date), MAX(date), COUNT(*) FROM visual.vsl_anly_stocks_price_subindex01')
        res = cur.fetchone()
        print(f"Range: {res[0]} ~ {res[1]} (Count: {res[2]})")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_range()
