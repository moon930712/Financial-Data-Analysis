import psycopg2
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def load_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env_vars[k] = v
    except: pass
    return env_vars

env = load_env()
conn = psycopg2.connect(
    host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
    dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
)

# Search for any theme with '은행' in the name
query1 = """
SELECT theme_name, COUNT(*) as stock_cnt
FROM industry.theme_name_list
WHERE theme_name LIKE '%은행%' OR theme_name LIKE '%금융%'
GROUP BY theme_name
ORDER BY stock_cnt DESC;
"""

df1 = pd.read_sql(query1, conn)
print("=== 테마 이름 검색 결과 (은행/금융) ===")
print(df1)

# Check specific '은행' theme stocks
query2 = """
SELECT stock_code, stock_name
FROM industry.theme_name_list
WHERE theme_name = '은행'
"""
df2 = pd.read_sql(query2, conn)
print("\n=== '은행' 테마 소속 종목 ===")
print(df2)

conn.close()
