import os
import psycopg2

def run_query():
    env = {}
    with open('.env') as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                env[k] = v

    conn = psycopg2.connect(
        host=env['DB_HOST'],
        port=env.get('DB_PORT', 5432),
        dbname=env['DB_NAME'],
        user=env['DB_USER'],
        password=env['DB_PASSWORD']
    )
    cur = conn.cursor()
    
    tables = [
        ('llm', 'naver_stock_report'),
        ('visual', 'vsl_anly_stocks_price_subindex03'),
        ('market', 'kosis_facility_investment_index')
    ]
    
    for schema, table in tables:
        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema='{schema}' AND table_name='{table}'")
        cols = [r[0] for r in cur.fetchall()]
        print(f"[{schema}.{table}] columns:", cols)

        # Print some sample data to see structure
        if cols:
            cur.execute(f"SELECT * FROM {schema}.{table} LIMIT 1")
            print("Sample data:", cur.fetchone())
            print()

    conn.close()

if __name__ == '__main__':
    run_query()
