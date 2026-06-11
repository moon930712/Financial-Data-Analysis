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

def run_phase_daily_returns_analysis():
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
        SELECT d0.date as base_date
             , d1.date as d1_date
             , d2.date as d2_date
             , d3.date as d3_date
             , d4.date as d4_date
             , d5.date as d5_date
        FROM valid_dates d0
        LEFT JOIN valid_dates d1 ON d1.rn = d0.rn + 1
        LEFT JOIN valid_dates d2 ON d2.rn = d0.rn + 2
        LEFT JOIN valid_dates d3 ON d3.rn = d0.rn + 3
        LEFT JOIN valid_dates d4 ON d4.rn = d0.rn + 4
        LEFT JOIN valid_dates d5 ON d5.rn = d0.rn + 5
        WHERE d0.date IN ({date_filter})
    )
    , stock_returns AS (
        SELECT m.base_date, p0.stock_code
             , p0.close as base_close
             , (p1.close - p0.close) / p0.close * 100 AS d1_return
             , (p2.close - p0.close) / p0.close * 100 AS d2_return
             , (p3.close - p0.close) / p0.close * 100 AS d3_return
             , (p4.close - p0.close) / p0.close * 100 AS d4_return
             , (p5.close - p0.close) / p0.close * 100 AS d5_return
        FROM date_mapping m
        JOIN visual.vsl_anly_stocks_price_subindex01 p0 ON p0.date = m.base_date
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p1 ON p1.date = m.d1_date AND p0.stock_code = p1.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p2 ON p2.date = m.d2_date AND p0.stock_code = p2.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p3 ON p3.date = m.d3_date AND p0.stock_code = p3.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p4 ON p4.date = m.d4_date AND p0.stock_code = p4.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p5 ON p5.date = m.d5_date AND p0.stock_code = p5.stock_code
        WHERE p0.close > 1000
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
    SELECT t.theme_name, p.date as base_date, p.stock_code, p.phase
         , r.d1_return, r.d2_return, r.d3_return, r.d4_return, r.d5_return
    FROM industry.theme_name_list t
    JOIN phase_calc p ON t.stock_code = p.stock_code
    JOIN stock_returns r ON r.base_date = p.date AND r.stock_code = p.stock_code
    """
    
    print("Fetching D+1 to D+5 stock returns from DB...")
    df_db = pd.read_sql(query, conn)
    df_db['base_date'] = df_db['base_date'].astype(str)
    conn.close()
    
    # Merge with target events
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
            if cnt == 0:
                continue
                
            results.append({
                'Pattern': pattern,
                'Phase': f'{phase}국면',
                'Stock Count': cnt,
                'D+1 Avg (%)': round(df_phase['d1_return'].mean(), 2),
                'D+1 Med (%)': round(df_phase['d1_return'].median(), 2),
                'D+2 Avg (%)': round(df_phase['d2_return'].mean(), 2),
                'D+2 Med (%)': round(df_phase['d2_return'].median(), 2),
                'D+3 Avg (%)': round(df_phase['d3_return'].mean(), 2),
                'D+3 Med (%)': round(df_phase['d3_return'].median(), 2),
                'D+4 Avg (%)': round(df_phase['d4_return'].mean(), 2),
                'D+4 Med (%)': round(df_phase['d4_return'].median(), 2),
                'D+5 Avg (%)': round(df_phase['d5_return'].mean(), 2),
                'D+5 Med (%)': round(df_phase['d5_return'].median(), 2),
            })
            
    df_res = pd.DataFrame(results)
    output_excel = 'pattern_phase_daily_returns.xlsx'
    df_res.to_excel(output_excel, index=False)
    
    print(f"\nDaily returns for phases saved to {output_excel}")

if __name__ == '__main__':
    run_phase_daily_returns_analysis()
