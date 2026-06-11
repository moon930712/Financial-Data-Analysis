import os
import psycopg2
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore', category=UserWarning)

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

env = load_env()

def run_research():
    print("Loading master statistics...")
    df_raw = pd.read_excel('pattern_consumer_stats_master.xlsx', sheet_name='Raw Data')
    
    target_patterns = [
        '6등급 -> 4등급 -> 1등급',
        '4등급 -> 3등급 -> 1등급',
        '4등급 -> 2등급 -> 2등급'
    ]
    
    df_target = df_raw[df_raw['Pattern'].isin(target_patterns)].copy()
    df_target['Date'] = df_target['Date'].astype(str)
    
    print(f"Total targeted events: {len(df_target)}")
    
    # DB 연결
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # 테마별 국면 분포를 집계하는 쿼리 (전체 기간)
    query = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2025-01-02' AND date <= '2026-05-15'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2024-12-01' AND m.date <= '2026-05-15'
    )
    , phase_calc AS (
        SELECT date, stock_code, stock_name
            , CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN 1
                WHEN histogram < 0 AND histogram <= lag_histogram THEN 2
                WHEN histogram >= 0 AND histogram > lag_histogram THEN 3
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4
                ELSE 4
            END AS phase
        FROM histo_base
        WHERE date IN (SELECT date FROM valid_dates)
    )
    SELECT nt.theme_name, p.date
        , COUNT(*) AS total_stocks
        , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) AS phase1_cnt
        , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) AS phase2_cnt
        , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) AS phase3_cnt
        , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) AS phase4_cnt
    FROM industry.theme_name_list nt 
    INNER JOIN phase_calc p ON nt.stock_code = p.stock_code
    GROUP BY nt.theme_name, p.date
    HAVING COUNT(*) >= 5
    """
    
    print("Fetching phase distribution from DB...")
    df_db = pd.read_sql(query, conn)
    df_db['date'] = df_db['date'].astype(str)
    
    conn.close()
    
    # 머지 (Event 매핑)
    df_merged = pd.merge(df_target, df_db, left_on=['Theme Name', 'Date'], right_on=['theme_name', 'date'], how='inner')
    
    print(f"Matched events: {len(df_merged)}")
    
    # 각 패턴별로 국면 분포의 평균 비율 구하기
    results = []
    for pattern in target_patterns:
        df_p = df_merged[df_merged['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        total_sum = df_p['total_stocks'].sum()
        p1_ratio = (df_p['phase1_cnt'].sum() / total_sum) * 100
        p2_ratio = (df_p['phase2_cnt'].sum() / total_sum) * 100
        p3_ratio = (df_p['phase3_cnt'].sum() / total_sum) * 100
        p4_ratio = (df_p['phase4_cnt'].sum() / total_sum) * 100
        
        results.append({
            'Pattern': pattern,
            'Event Count': len(df_p),
            'Total Stocks': total_sum,
            'Phase 1 (회복기) %': round(p1_ratio, 2),
            'Phase 2 (하락기) %': round(p2_ratio, 2),
            'Phase 3 (상승기) %': round(p3_ratio, 2),
            'Phase 4 (후퇴기) %': round(p4_ratio, 2)
        })
        
    df_res = pd.DataFrame(results)
    print("\n=== 패턴별 소속 종목들의 국면(Phase) 평균 분포 ===")
    print(df_res.to_string(index=False))

if __name__ == '__main__':
    run_research()
