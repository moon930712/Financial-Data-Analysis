import os
import psycopg2
import pandas as pd

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    try:
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip()
                    except: pass
load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def analyze_defense_shipbuilding():
    conn = get_connection()
    # 방산: 한화에어로스페이스(012450), LIG넥스원(079550)
    # 조선: HD현대중공업(329180), 삼성중공업(010140)
    codes = ('012450', '079550', '329180', '010140')
    
    # 1. 2024~2025 ROE, PBR 추이 분석
    q_fundamental = f"""
    SELECT code, date, pbr, per 
    FROM company.krx_stocks_fundamental_info 
    WHERE code IN {codes} AND date >= '2024-01-01' AND date <= '2025-04-01'
    ORDER BY code, date;
    """
    df_f = pd.read_sql_query(q_fundamental, conn)
    
    # 2. 리포트 빈도 분석
    q_reports = f"""
    SELECT code, date, title 
    FROM llm.naver_stock_report 
    WHERE code IN {codes} AND date >= '2024-01-01' AND date <= '2025-04-01'
    """
    df_r = pd.read_sql_query(q_reports, conn)
    
    conn.close()
    
    print("=== Fundamental Trends (Mean by Quarter) ===")
    df_f['date'] = pd.to_datetime(df_f['date'])
    df_f['q'] = df_f['date'].dt.to_period('Q')
    print(df_f.groupby(['code', 'q'])[['pbr', 'per']].mean())
    
    print("\n=== Report Frequency by Month ===")
    df_r['date'] = pd.to_datetime(df_r['date'])
    df_r['m'] = df_r['date'].dt.to_period('M')
    print(df_r.groupby(['code', 'm']).size())

if __name__ == "__main__":
    analyze_defense_shipbuilding()
