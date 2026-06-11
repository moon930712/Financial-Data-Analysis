import os
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
    # Read the SQL query
    with open('extract_target_patterns.sql', 'r', encoding='utf-8') as f:
        query = f.read()

    # The SQL query uses a variable ${date:sqlstring}. Let's replace it with NULL so it defaults to max date.
    query = query.replace("${date:sqlstring}", "NULL")

    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    print("Executing extract_target_patterns.sql...")
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"Total extracted rows: {len(df)}")
    
    if len(df) > 0:
        print("\n=== 패턴별 분포 ===")
        pattern_counts = df['패턴'].value_counts()
        print(pattern_counts.to_string())
        
        print("\n=== 전일(Day-1) 등급별 분포 ===")
        # 패턴의 중간 등급 추출 (예: '6등급 -> 4등급 -> 1등급' 에서 '4등급')
        df['전일 등급'] = df['패턴'].apply(lambda x: x.split('->')[1].strip())
        day1_counts = df['전일 등급'].value_counts()
        for grade, count in day1_counts.items():
            print(f"{grade}: {count}건 ({count/len(df)*100:.1f}%)")
    else:
        print("추출된 데이터가 없습니다.")

if __name__ == "__main__":
    main()
