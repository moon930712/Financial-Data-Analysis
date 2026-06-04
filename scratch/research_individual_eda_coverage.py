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
        host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD')
    )

def check_coverage():
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(DISTINCT stock_code) FROM visual.vsl_anly_stocks_price_subindex01")
    price_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT code) FROM company.krx_stocks_fundamental_info")
    fundamental_count = cur.fetchone()[0]
    
    print(f"Price Table Count: {price_count}")
    print(f"Fundamental Table Count: {fundamental_count}")
    
    # Check if we have price data for 2024-01-02 and 2025-01-02
    cur.execute("SELECT COUNT(*) FROM visual.vsl_anly_stocks_price_subindex01 WHERE date = '2024-01-02'")
    date1_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM visual.vsl_anly_stocks_price_subindex01 WHERE date = '2025-01-02'")
    date2_count = cur.fetchone()[0]
    
    print(f"Stocks on 2024-01-02: {date1_count}")
    print(f"Stocks on 2025-01-02: {date2_count}")
    
    conn.close()

if __name__ == "__main__":
    check_coverage()
