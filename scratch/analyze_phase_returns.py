import os
import psycopg2
import pandas as pd
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

def run_phase_returns_analysis():
    print("Loading target events from master Excel...")
    df_raw = pd.read_excel('pattern_consumer_stats_master.xlsx', sheet_name='Raw Data')
    
    target_patterns = [
        '6등급 -> 4등급 -> 1등급',
        '4등급 -> 3등급 -> 1등급',
        '4등급 -> 2등급 -> 2등급'
    ]
    
    df_target = df_raw[df_raw['Pattern'].isin(target_patterns)].copy()
    df_target['Date'] = df_target['Date'].astype(str)
    
    target_dates = df_target['Date'].unique().tolist()
    date_filter = "'" + "', '".join(target_dates) + "'"
    
    print(f"Total targeted events: {len(df_target)}, Unique dates: {len(target_dates)}")
    
    # DB 연결
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    query = f"""
    WITH valid_dates AS (
        SELECT date, ROW_NUMBER() OVER(ORDER BY date) as rn
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE stock_code = '005930' 
          AND date >= '2024-12-01' AND date <= '2026-05-31'
    )
    , date_mapping AS (
        SELECT d1.date as base_date, d2.date as future_date
        FROM valid_dates d1
        JOIN valid_dates d2 ON d2.rn = d1.rn + 5
        WHERE d1.date IN ({date_filter})
    )
    , stock_returns AS (
        SELECT m.base_date, p1.stock_code
             , p1.close as base_close
             , p2.close as future_close
             , (p2.close - p1.close) / p1.close * 100 AS d5_return
        FROM date_mapping m
        JOIN visual.vsl_anly_stocks_price_subindex01 p1 ON p1.date = m.base_date
        JOIN visual.vsl_anly_stocks_price_subindex01 p2 ON p2.date = m.future_date AND p1.stock_code = p2.stock_code
        WHERE p1.close > 1000
    )
    , histo_base AS (
        SELECT m.date, m.stock_code
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2024-12-01' AND m.date <= '2026-05-31'
    )
    , phase_calc AS (
        SELECT date, stock_code
            , CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN 1
                WHEN histogram < 0 AND histogram <= lag_histogram THEN 2
                WHEN histogram >= 0 AND histogram > lag_histogram THEN 3
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4
                ELSE 4
            END AS phase
        FROM histo_base
        WHERE date IN ({date_filter})
    )
    SELECT t.theme_name, p.date as base_date, p.stock_code, p.phase, r.d5_return
    FROM industry.theme_name_list t
    JOIN phase_calc p ON t.stock_code = p.stock_code
    JOIN stock_returns r ON r.base_date = p.date AND r.stock_code = p.stock_code
    """
    
    print("Fetching stock level returns and phases from DB...")
    df_db = pd.read_sql(query, conn)
    df_db['base_date'] = df_db['base_date'].astype(str)
    conn.close()
    
    # Merge with target events to filter only the themes we care about on those dates
    df_merged = pd.merge(df_target[['Pattern', 'Theme Name', 'Date']], 
                         df_db, 
                         left_on=['Theme Name', 'Date'], 
                         right_on=['theme_name', 'base_date'], 
                         how='inner')
                         
    print(f"Matched individual stock events: {len(df_merged)}")
    
    results = []
    
    for pattern in target_patterns:
        df_p = df_merged[df_merged['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        for phase in [1, 2, 3, 4]:
            df_phase = df_p[df_p['phase'] == phase]
            cnt = len(df_phase)
            avg_ret = df_phase['d5_return'].mean() if cnt > 0 else 0.0
            med_ret = df_phase['d5_return'].median() if cnt > 0 else 0.0
            
            results.append({
                'Pattern': pattern,
                'Phase': phase,
                'Stock Count': cnt,
                'Avg Return (%)': round(avg_ret, 2),
                'Med Return (%)': round(med_ret, 2)
            })
            
    df_res = pd.DataFrame(results)
    print("\n=== 패턴별/국면별 소속 종목들의 D+5 수익률 ===")
    print(df_res.to_string(index=False))

if __name__ == '__main__':
    run_phase_returns_analysis()
