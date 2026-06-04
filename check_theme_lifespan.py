import os
import psycopg2
import pandas as pd

def load_env(filepath):
    if not os.path.exists(filepath):
        print(f"{filepath} not found.")
        return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('.env')

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

try:
    # 1. 네이버 테마 테이블의 컬럼 확인
    query_columns = """
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'company' AND table_name = 'naver_theme'
    """
    cols_df = pd.read_sql_query(query_columns, conn)
    columns = cols_df['column_name'].tolist()
    
    if 'date' in columns or 'base_date' in columns or 'std_date' in columns or 'create_date' in columns:
        date_col = 'date' if 'date' in columns else ('base_date' if 'base_date' in columns else ('std_date' if 'std_date' in columns else 'create_date'))
        
        query_lifespan = f"""
        SELECT 
            theme_name, 
            MIN({date_col}) as first_appearance, 
            MAX({date_col}) as last_appearance,
            MAX({date_col}) - MIN({date_col}) as lifespan_days,
            COUNT(DISTINCT stock_code) as stocks_count
        FROM company.naver_theme
        GROUP BY theme_name
        HAVING (MAX({date_col}) - MIN({date_col})) > 0 AND (MAX({date_col}) - MIN({date_col})) <= 90
        ORDER BY lifespan_days ASC
        LIMIT 15;
        """
        df = pd.read_sql_query(query_lifespan, conn)
        print("=== 90일(3개월) 이내에 생성되었다가 소멸한 단기 테마 목록 ===")
        if df.empty:
            print("데이터베이스에 90일 이내에 단명한 테마가 없거나 수집 기간이 부족합니다.")
        else:
            print(df.to_string())
    else:
        print("naver_theme 테이블에 날짜(date) 컬럼이 존재하지 않아 수명(Lifespan) 분석이 불가합니다.")
        print(f"현재 컬럼 목록: {columns}")
        
finally:
    conn.close()
