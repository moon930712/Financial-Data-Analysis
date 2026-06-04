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

def investigate_results():
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Check data for (CURRENT_DATE - INTERVAL '1 year')
    cur.execute("SELECT (CURRENT_DATE - INTERVAL '1 year')::date")
    target_date = cur.fetchone()[0]
    cur.execute("SELECT COUNT(code) FROM company.krx_stocks_fundamental_info WHERE date = (CURRENT_DATE - INTERVAL '1 year')::date")
    count_1yr = cur.fetchone()[0]
    print(f"Target Date: {target_date}, Count: {count_1yr}")
    
    # 2. Check current max date
    cur.execute("SELECT MAX(date) FROM company.krx_stocks_fundamental_info")
    max_date = cur.fetchone()[0]
    print(f"Latest Date in DB: {max_date}")

    # 3. Running original query logic logic
    query_2024 = """
    SELECT ib.wics_name, MIN(fb.pbr) as pbr_min, MAX(fb.pbr) as pbr_max
    FROM visual.vsl_anly_stocks_price_subindex01 ib
    JOIN company.krx_stocks_fundamental_info fb ON ib.stock_code = fb.code
    WHERE fb.date >= '2024-01-01'
    GROUP BY ib.wics_name LIMIT 5
    """
    cur.execute(query_2024)
    print("\n2024-Present Range Logic:")
    for row in cur.fetchall():
        print(row)

    # 4. Running user's changed logic
    query_user = """
    SELECT ib.wics_name, MIN(fb.pbr) as pbr_min, MAX(fb.pbr) as pbr_max
    FROM visual.vsl_anly_stocks_price_subindex01 ib
    JOIN company.krx_stocks_fundamental_info fb ON ib.stock_code = fb.code
    WHERE fb.date = (CURRENT_DATE - INTERVAL '1 year')::date
    GROUP BY ib.wics_name LIMIT 5
    """
    cur.execute(query_user)
    print("\nUser's 'Just 1 Year Ago' Logic:")
    for row in cur.fetchall():
        print(row)
    
    conn.close()

if __name__ == "__main__":
    investigate_results()
