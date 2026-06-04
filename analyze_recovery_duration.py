import os
import psycopg2
import pandas as pd

def load_env(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

def get_connection():
    load_env('.env')
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def run_recovery_analysis():
    conn = get_connection()
    try:
        sql_path = os.path.join('src', 'sql', 'recovery_phase_analysis.sql')
        with open(sql_path, 'r', encoding='utf-8') as f:
            query = f.read()
        
        print("회복기(Phase 1) 데이터 분석 중...")
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("데이터가 없습니다.")
            return

        # 중분류별 회복기 평균 지속일수
        stats = df.groupby('중분류')['회복기지속일수'].agg(['mean', 'median', 'count']).reset_index()
        stats = stats.sort_values(by='mean', ascending=False)
        
        print("\n[ 업종별 회복기(Phase 1) 평균 유예 기간 ]")
        print(stats.head(20))
        
        stats.to_csv('result/recovery_phase_stats.csv', encoding='utf-8-sig', index=False)
        
        total_avg = df['회복기지속일수'].mean()
        print(f"\n전체 종목 회복기 평균: {total_avg:.2f}일")

    finally:
        conn.close()

if __name__ == "__main__":
    run_recovery_analysis()
