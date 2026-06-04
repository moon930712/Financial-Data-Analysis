import os
import psycopg2
import pandas as pd

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def research_peak_price_performance():
    conn = get_connection()
    
    # 1. 업종별 2024년 이후 최고 PBR과 그 시점의 날짜 찾기
    query_max_pbr = """
    WITH sector_pbr AS (
        SELECT ib.wics_name, fb.date, fb.pbr,
               ROW_NUMBER() OVER(PARTITION BY ib.wics_name ORDER BY fb.pbr DESC) as rn
        FROM company.krx_stocks_fundamental_info fb
        JOIN visual.vsl_anly_stocks_price_subindex01 ib ON fb.code = ib.stock_code
        WHERE fb.date >= '2024-01-01'
    )
    SELECT wics_name, date as max_pbr_date, pbr as max_pbr
    FROM sector_pbr
    WHERE rn = 1
    """
    df_max_pbr = pd.read_sql_query(query_max_pbr, conn)
    
    # 2. 업종별 각 날짜의 평균 종가 (지수 대용) 가져오는 함수 정의
    results = []
    current_date = pd.read_sql_query("SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01", conn).iloc[0,0]
    
    for _, row in df_max_pbr.iterrows():
        sector = row['wics_name']
        max_date = row['max_pbr_date']
        
        # 피크 시점 가격 (평균 종가)
        query_peak_price = f"""
        SELECT AVG(close) as avg_price
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE wics_name = %s AND date = %s
        """
        peak_price = pd.read_sql_query(query_peak_price, conn, params=(sector, max_date)).iloc[0,0]
        
        # 현재 시점 가격
        query_current_price = f"""
        SELECT AVG(close) as avg_price
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE wics_name = %s AND date = %s
        """
        curr_price = pd.read_sql_query(query_current_price, conn, params=(sector, current_date)).iloc[0,0]
        
        if peak_price and curr_price:
            perf = (curr_price / peak_price - 1) * 100
            results.append({
                'sector': sector,
                'max_pbr_date': max_date,
                'max_pbr': row['max_pbr'],
                'peak_price': peak_price,
                'current_price': curr_price,
                'performance_pct': perf
            })
            
    df_final = pd.DataFrame(results)
    df_final.to_csv(r'c:\Users\Hubnet\antigravity\results\sector_peak_performance.csv', index=False, encoding='utf-8-sig')
    print("Peak performance research completed.")
    print(df_final.head(10))
    conn.close()

if __name__ == "__main__":
    research_peak_price_performance()
