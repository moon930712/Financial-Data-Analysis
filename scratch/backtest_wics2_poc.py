import os
import psycopg2
import pandas as pd

def load_env():
    with open('c:/Users/Hubnet/antigravity/.env', 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env()

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

try:
    # 1. 쿼리 로드
    sql_path = 'c:/Users/Hubnet/antigravity/src/sql/sector_wics2_phase_group1_2_vs_3_4.sql'
    with open(sql_path, 'r', encoding='utf-8') as f:
        query = f.read()
    
    # 2. 기준일자 변경 (MAX(date) -> 특정 과거 시점, 예: 2026-01-20)
    past_date = '2026-01-20'
    
    # 쿼리의 date = (SELECT MAX(date)... 부분 치환
    query = query.replace("date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02)", f"date = '{past_date}'")
    
    # 3. 과거 시점의 랭킹 산출
    print(f"[{past_date}] 기준 WICS 중분류 랭킹 추출 중...")
    df_rank = pd.read_sql_query(query, conn)
    
    # 상위 3개 주도 업종 (g2_ratio 가장 높은 것)
    df_sorted = df_rank.sort_values(by='0선위(상승+둔화)비율(%)', ascending=False)
    top_3_sectors = df_sorted.head(3)['업종명(WICS중분류)'].tolist()
    
    # 하위 3개 소외 업종 (g1_ratio 가장 낮은 것, 즉 파란색 가장 많은 것)
    bottom_3_sectors = df_sorted.tail(3)['업종명(WICS중분류)'].tolist()
    
    print(f"-> 3개월 전 예측된 주도 업종 Top 3: {top_3_sectors}")
    print(f"-> 3개월 전 예측된 소외 업종 Bottom 3: {bottom_3_sectors}")
    
    # 4. 3개월 후(최근일) 수익률 실제 검증
    # WICS2에 속한 종목들의 past_date 대비 현재 수익률 산출
    verify_query = f"""
    WITH target_stocks AS (
        SELECT stock_code, wics_name2
        FROM visual.vsl_krx_stocks_cap
        WHERE wics_name2 IN %s
    ),
    prices AS (
        SELECT 
            stock_code,
            date,
            close
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '{past_date}'
    ),
    start_prices AS (
        SELECT stock_code, close AS start_price
        FROM prices
        WHERE date = '{past_date}'
    ),
    end_prices AS (
        SELECT stock_code, close AS end_price
        FROM prices
        WHERE date = (SELECT MAX(date) FROM prices)
    )
    SELECT 
        ts.wics_name2,
        ROUND(AVG((e.end_price - s.start_price) / s.start_price * 100), 2) AS avg_return_pct
    FROM target_stocks ts
    JOIN start_prices s ON ts.stock_code = s.stock_code
    JOIN end_prices e ON ts.stock_code = e.stock_code
    GROUP BY ts.wics_name2
    ORDER BY avg_return_pct DESC;
    """
    
    all_sectors = tuple(top_3_sectors + bottom_3_sectors)
    df_returns = pd.read_sql_query(verify_query, conn, params=(all_sectors,))
    
    with open('c:/Users/Hubnet/antigravity/scratch/result_poc.txt', 'w', encoding='utf-8') as f:
        f.write(f"[수익률 검증 결과 (2026-01-20 -> 현재)]\n")
        f.write(f"-> 3개월 전 예측된 주도 업종 Top 3: {top_3_sectors}\n")
        f.write(f"-> 3개월 전 예측된 소외 업종 Bottom 3: {bottom_3_sectors}\n\n")
        
        for _, row in df_returns.iterrows():
            sector = row['wics_name2']
            ret = row['avg_return_pct']
            group = "[주도 예측]" if sector in top_3_sectors else "[소외 예측]"
            f.write(f"{group} {sector}: {ret}%\n")
    print("Done")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
