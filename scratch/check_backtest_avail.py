import psycopg2
import os
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

def check_historical_data():
    conn = get_connection()
    
    # 1. Check PBR historical range
    query_pbr = "SELECT MIN(date), MAX(date), COUNT(*) FROM company.krx_stocks_fundamental_info"
    pbr_info = pd.read_sql_query(query_pbr, conn)
    print("PBR Range and Count:")
    print(pbr_info)
    
    # 2. Check ROE reference months (Historical ROE check)
    query_roe = "SELECT referenceyearmonth, COUNT(*) FROM company.kis_kospi_info GROUP BY referenceyearmonth ORDER BY referenceyearmonth"
    roe_info = pd.read_sql_query(query_roe, conn)
    print("\nROE Reference Months (KOSPI):")
    print(roe_info)
    
    # 3. Check Sector Price range
    query_price = "SELECT MIN(date), MAX(date) FROM visual.vsl_anly_stocks_price_subindex01"
    price_info = pd.read_sql_query(query_price, conn)
    print("\nSector Price Range:")
    print(price_info)
    
    conn.close()

if __name__ == "__main__":
    check_historical_data()
