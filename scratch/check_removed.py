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

env = load_env()
conn = psycopg2.connect(
    host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
    dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
)

df = pd.read_excel('backtest_extract_target_patterns_with_rsi_filtered.xlsx')

print('--- Removed Stocks (Close >= Open * 1.10) ---')
count = 0
for idx, row in df.iterrows():
    dt = row['Signal Date']
    sname = row['Stock Name']
    q = f"""
        SELECT v1.open, v1.close, v1.stock_code
        FROM visual.vsl_anly_stocks_price_subindex01 v1
        JOIN industry.theme_name_list nl ON v1.stock_code = nl.stock_code
        WHERE nl.stock_name = '{sname}' AND v1.date = '{dt}'
        LIMIT 1
    """
    df_price = pd.read_sql(q, conn)
    if not df_price.empty:
        o = df_price.iloc[0]['open']
        c = df_price.iloc[0]['close']
        code = df_price.iloc[0]['stock_code']
        if o > 0 and c >= o * 1.10:
            diff_pct = ((c - o) / o) * 100
            print(f"Date: {dt} | Code: {code} | Open: {o} | Close: {c} | Rose: {diff_pct:.2f}%")
            count += 1

print(f'Total {count} stocks removed.')
conn.close()
