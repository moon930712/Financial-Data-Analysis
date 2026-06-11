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

def main():
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    query = """
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_schema IN ('visual', 'industry', 'public')
    ORDER BY table_schema, table_name;
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    weekly_candidates = df[df['table_name'].str.contains('week|wk|주봉', case=False, na=False)]
    
    print("=== All Tables ===")
    for _, row in df.iterrows():
        print(f"{row['table_schema']}.{row['table_name']}")
        
    print("\n=== Weekly Candidates ===")
    if weekly_candidates.empty:
        print("No tables found with 'week', 'wk', or '주봉' in the name.")
    else:
        for _, row in weekly_candidates.iterrows():
            print(f"{row['table_schema']}.{row['table_name']}")

if __name__ == "__main__":
    main()
