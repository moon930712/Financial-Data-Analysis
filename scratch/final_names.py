import pandas as pd
import psycopg2
import json

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
codes_str = ','.join([f"'{c}'" for c in codes])
q = f"SELECT stock_code, stock_name FROM industry.theme_name_list WHERE stock_code IN ({codes_str})"
df = pd.read_sql(q, conn)
res = df.drop_duplicates().to_dict('records')

with open('scratch/names.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
