import psycopg2, os
def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
load_env()
conn = psycopg2.connect(host=os.environ.get('DB_HOST'), port=os.environ.get('DB_PORT', 5432), dbname=os.environ.get('DB_NAME'), user=os.environ.get('DB_USER'), password=os.environ.get('DB_PASSWORD'))
cur = conn.cursor()

print("KOSPI Data (first 5):")
cur.execute("SELECT shortcode, koreanname, marketcap FROM company.kis_kospi_info WHERE marketcap IS NOT NULL AND marketcap > 0 LIMIT 5")
print(cur.fetchall())

print("\nKOSDAQ Data (first 5):")
cur.execute("SELECT shortcode, koreanname, previousdaymarketcap FROM company.kis_kosdaq_info WHERE previousdaymarketcap IS NOT NULL AND previousdaymarketcap > 0 LIMIT 5")
print(cur.fetchall())

conn.close()
