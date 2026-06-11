import os
import psycopg2
import pandas as pd
import numpy as np
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
    print("Loading day_minus_2_raw.csv...")
    df_themes = pd.read_csv('scratch/day_minus_2_raw.csv')
    
    # 분석 속도를 위해 grade별로 균등하게 1000개씩 샘플링해서 분석 (전체 데이터가 10만건이라 DB 쿼리가 오래 걸림)
    # Success는 적으므로 전부 가져오고, Failure는 샘플링
    df_themes['is_success'] = df_themes['future_grade_d2'] == '1등급'
    df_success = df_themes[df_themes['is_success']]
    df_fail = df_themes[~df_themes['is_success']].sample(n=min(len(df_success)*2, len(df_themes[~df_themes['is_success']])), random_state=42)
    
    df_sample = pd.concat([df_success, df_fail])
    print(f"Sampled {len(df_sample)} rows for stock-level analysis (Success: {len(df_success)}, Failure: {len(df_fail)})")
    
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # 임시 테이블에 샘플 데이터 밀어넣기
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TEMP TABLE temp_theme_sample (
            date DATE,
            theme_name VARCHAR(100),
            is_success BOOLEAN,
            grade VARCHAR(20)
        )
    """)
    
    from psycopg2.extras import execute_values
    data_tuples = [(row['date'], row['theme_name'], row['is_success'], row['grade']) for _, row in df_sample.iterrows()]
    execute_values(cursor, "INSERT INTO temp_theme_sample (date, theme_name, is_success, grade) VALUES %s", data_tuples)
    conn.commit()
    
    # 각 테마/날짜별 대장주(당일 거래대금 1위 종목)의 지표를 가져오는 쿼리
    query = """
    WITH theme_stocks AS (
        SELECT 
            t.date, t.theme_name, t.is_success, t.grade,
            nt.stock_code,
            v1.trade_value, v1.ma20, v1.close,
            v2.rsi,
            LAG(v1.trade_value, 1) OVER(PARTITION BY nt.stock_code ORDER BY v1.date) as lag_trade_value
        FROM temp_theme_sample t
        JOIN industry.theme_name_list nt ON t.theme_name = nt.theme_name
        JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON nt.stock_code = v1.stock_code AND v1.date = t.date
        JOIN visual.vsl_anly_stocks_price_subindex02 v2 ON nt.stock_code = v2.stock_code AND v2.date = t.date
    )
    , top_stocks AS (
        SELECT *
        FROM (
            SELECT *,
                ROW_NUMBER() OVER(PARTITION BY date, theme_name ORDER BY trade_value DESC) as rnk
            FROM theme_stocks
        ) A
        WHERE rnk = 1
    )
    SELECT 
        ts.date, ts.theme_name, ts.is_success, ts.grade, ts.stock_code,
        ts.rsi, 
        (ts.close / NULLIF(ts.ma20, 0)) * 100 as disparity_20,
        CASE WHEN ts.lag_trade_value > 0 THEN ts.trade_value / ts.lag_trade_value ELSE 1 END as volume_spike
    FROM top_stocks ts
    """
    
    print("Fetching stock-level data...")
    df_stocks = pd.read_sql(query, conn)
    
    # Smart Money (최근 3일 외인/기관 합산) 계산 로직 추가
    # 대장주의 Smart Money를 한방에 가져오기 위한 쿼리
    query_sm = """
    SELECT 
        ts.date, ts.stock_code,
        SUM(CASE WHEN k.investor IN ('기관합계', '외국인') THEN k.net_trade_vol ELSE 0 END) as sm_flow
    FROM top_stocks ts
    JOIN visual.vsl_krx_stocks_investor_shares_trading_info k 
      ON ts.stock_code = k.stock_code 
     AND k.date <= ts.date 
     AND k.date >= ts.date - INTERVAL '4 days' -- 넉넉히 최근 3영업일 잡기 위해
    GROUP BY ts.date, ts.stock_code
    """
    # 임시 테이블 생성 시 top_stocks가 WITH 절 안에 있었으므로, 
    # 차라리 df_stocks를 구한 뒤, pandas로 합치기 위해 stock_code/date 목록을 다시 임시테이블에 넣는게 빠릅니다.
    
    cursor.execute("""
        CREATE TEMP TABLE temp_top_stocks (
            date DATE,
            stock_code VARCHAR(20)
        )
    """)
    stock_tuples = [(row['date'], row['stock_code']) for _, row in df_stocks.iterrows()]
    execute_values(cursor, "INSERT INTO temp_top_stocks (date, stock_code) VALUES %s", stock_tuples)
    conn.commit()
    
    query_sm2 = """
    SELECT 
        t.date, t.stock_code,
        SUM(CASE WHEN k.investor IN ('기관합계', '외국인') THEN k.net_trade_vol ELSE 0 END) as sm_flow
    FROM temp_top_stocks t
    JOIN visual.vsl_krx_stocks_investor_shares_trading_info k 
      ON t.stock_code = k.stock_code 
     AND k.date <= t.date 
     AND k.date >= t.date - INTERVAL '5 days' 
    GROUP BY t.date, t.stock_code
    """
    df_sm = pd.read_sql(query_sm2, conn)
    conn.close()
    
    # Merge
    df_final = pd.merge(df_stocks, df_sm, on=['date', 'stock_code'], how='left')
    df_final['sm_flow'] = df_final['sm_flow'].fillna(0)
    
    print("\n=== 종목(대장주) 단위 분석 (Success vs Failure) ===")
    
    for grade in ['6등급', '4등급', '3등급']:
        df_g = df_final[df_final['grade'] == grade]
        if df_g.empty: continue
        
        succ = df_g[df_g['is_success']]
        fail = df_g[~df_g['is_success']]
        
        print(f"\n[{grade} 대장주 특성]")
        print(f"Success N={len(succ)}, Failure N={len(fail)}")
        
        features = ['rsi', 'disparity_20', 'volume_spike', 'sm_flow']
        
        for f in features:
            s_mean = succ[f].mean()
            f_mean = fail[f].mean()
            diff = s_mean - f_mean
            print(f"  - {f}: Success = {s_mean:.2f} / Failure = {f_mean:.2f} (Diff: {diff:.2f})")

if __name__ == "__main__":
    main()
