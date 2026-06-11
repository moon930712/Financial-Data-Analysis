import pandas as pd
import psycopg2

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

conn = psycopg2.connect(
    host=load_env().get('DB_HOST', 'localhost'), port=load_env().get('DB_PORT', 15432),
    dbname=load_env().get('DB_NAME', 'postgres'), user=load_env().get('DB_USER', 'postgres'), password=load_env().get('DB_PASSWORD', 'postgres')
)
codes = ['160980', '023160', '017960', '006360', '243840', '348370', '122640', '005290']
q = f"SELECT stock_code, stock_name FROM industry.theme_name_list WHERE stock_code IN ({','.join([repr(c) for c in codes])})"
df = pd.read_sql(q, conn)
for idx, row in df.drop_duplicates().iterrows():
    print(row['stock_code'], row['stock_name'])
