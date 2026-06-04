import os
import psycopg2
import pandas as pd

def load_env(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

def get_connection():
    load_env('.env')
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def screen():
    conn = get_connection()
    try:
        # Load sector ranking first
        with open('src/sql/stock_phase_master.sql', 'r', encoding='utf-8') as f:
            sector_query = f.read().replace('${wics_name2:sqlstring}', "'All'")
        
        df_sector = pd.read_sql_query(sector_query, conn)
        top_sectors = df_sector.head(5)['소분류명'].tolist()
        print(f"Top 5 Sectors: {top_sectors}")

        # Load stock details
        with open('src/sql/stock_sector_phase_master.sql', 'r', encoding='utf-8') as f:
            stock_query_tpl = f.read()
        
        print("\n[ 후보 종목 리스트 ]")
        for sector in top_sectors + ['전기장비', '생명보험', '증권']:
            q = stock_query_tpl.replace('${wics_name:sqlstring}', f"'{sector}'")
            df_stocks = pd.read_sql_query(q, conn)
            if not df_stocks.empty:
                print(f"\n--- {sector} ---")
                print(df_stocks.head(5).to_string(index=False))

    finally:
        conn.close()

if __name__ == "__main__":
    screen()
