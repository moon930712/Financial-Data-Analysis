import os
import psycopg2
from decimal import Decimal

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

def test_sql():
    sql_path = r'c:\Users\Hubnet\antigravity\src\sql\industry_zscore_ranking.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        query = f.read()
    
    # Remove any UI variables if exists (e.g. $wics_name) or comment them out
    # Currently line 55 is commented out: --  and s.wics_name IN ($wics_name)
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        print("Executing SQL query...")
        cur.execute(query)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        print(f"Results found: {len(rows)}")
        if rows:
            print(" | ".join(colnames))
            for row in rows[:5]:
                print(" | ".join(str(val) for val in row))
            if len(rows) > 5:
                print("...")
        else:
            print("No results returned! Checking data availability...")
            
            cur.execute("SELECT MAX(date) FROM company.krx_stocks_fundamental_info")
            max_fundamental = cur.fetchone()[0]
            print(f"Max date in krx_stocks_fundamental_info: {max_fundamental}")
            
            cur.execute("SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01")
            max_price = cur.fetchone()[0]
            print(f"Max date in vsl_anly_stocks_price_subindex01: {max_price}")
            
            cur.execute("SELECT COUNT(*) FROM company.kis_kospi_info WHERE roe IS NOT NULL AND roe > 0")
            plus_roe_kospi = cur.fetchone()[0]
            print(f"Positive ROE (KOSPI): {plus_roe_kospi}")
            
            cur.execute("SELECT COUNT(*) FROM company.kis_kosdaq_info WHERE roe IS NOT NULL AND roe > 0")
            plus_roe_kosdaq = cur.fetchone()[0]
            print(f"Positive ROE (KOSDAQ): {plus_roe_kosdaq}")

    except Exception as e:
        print(f"Error during execution: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    test_sql()
