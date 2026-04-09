import os, psycopg2, pandas as pd

[os.environ.setdefault(k,v) for line in open('.env') if '=' in line for k,v in [line.strip().split('=',1)]]
conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', 5432), dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])

print('--- kis_kospi_info ALL columns ---')
try:
    q = "SELECT column_name FROM information_schema.columns WHERE table_name = 'kis_kospi_info' AND table_schema = 'company';"
    cols = pd.read_sql_query(q, conn)
    print(cols['column_name'].tolist())
except Exception as e:
    print(e)
conn.close()
