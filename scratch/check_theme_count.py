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
def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST')
        , port=os.environ.get('DB_PORT', 5432)
        , dbname=os.environ.get('DB_NAME')
        , user=os.environ.get('DB_USER')
        , password=os.environ.get('DB_PASSWORD')
    )
try:
    conn = get_connection()
    cur = conn.cursor()
    theme_name = '전자파'
    cur.execute("SELECT COUNT(DISTINCT stock_code) FROM company.naver_theme WHERE theme_name = %s", (theme_name,))
    count = cur.fetchone()[0]
    cur.execute("SELECT DISTINCT stock_name FROM company.naver_theme WHERE theme_name = %s", (theme_name,))
    stocks = [row[0] for row in cur.fetchall()]
    print(f"Theme: {theme_name}")
    print(f"Total Unique Stocks: {count}")
    print(f"Stock Names: {stocks}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
