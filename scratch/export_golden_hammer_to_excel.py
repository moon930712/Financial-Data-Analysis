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
    query_base = """
    WITH all_valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2023-10-01' 
    )
    , theme_histo_base AS (
        SELECT 
            m.date
            , m.stock_code
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date IN (SELECT date FROM all_valid_dates)
    )
    , theme_phase_classification AS (
        SELECT 
            date
            , stock_code
            , histogram
            , CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN 1 
                WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 
                WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 
                ELSE 4 
              END as phase
        FROM theme_histo_base
    )
    , theme_aggregation AS (
        SELECT 
            nt.theme_name
            , p.date
            , COUNT(*) as total_cnt
            , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
            , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt
            , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt
            , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
        FROM industry.theme_name_list nt
        INNER JOIN theme_phase_classification p ON nt.stock_code = p.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
        WHERE v1.close > 1000 
        GROUP BY nt.theme_name, p.date
        HAVING COUNT(*) >= 5
    )
    , final_ranking AS (
        SELECT date, theme_name
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                total_cnt DESC
              ) AS global_rank
        FROM theme_aggregation
    )
    , theme_grades AS (
        SELECT 
            date, theme_name
            , CASE 
                WHEN global_rank <= 25 THEN '1등급' 
                WHEN global_rank <= 50 THEN '2등급' 
                WHEN global_rank <= 75 THEN '3등급' 
                WHEN global_rank <= 100 THEN '4등급' 
                WHEN global_rank <= 125 THEN '5등급' 
                ELSE '6등급' 
              END AS grade
        FROM final_ranking
    )
    , price_data AS (
        SELECT 
            date, stock_code, close,
            LEAD(close, 1) OVER(PARTITION BY stock_code ORDER BY date) as close_d1,
            LEAD(close, 2) OVER(PARTITION BY stock_code ORDER BY date) as close_d2,
            LEAD(close, 3) OVER(PARTITION BY stock_code ORDER BY date) as close_d3,
            LEAD(close, 4) OVER(PARTITION BY stock_code ORDER BY date) as close_d4,
            LEAD(close, 5) OVER(PARTITION BY stock_code ORDER BY date) as close_d5
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '2023-10-01'
    )
    SELECT 
        p.date, p.stock_code, nt.stock_name, nt.theme_name, g.grade,
        p.histogram, p.phase,
        v1.close, v1.close_d1, v1.close_d2, v1.close_d3, v1.close_d4, v1.close_d5
    FROM theme_phase_classification p
    JOIN industry.theme_name_list nt ON p.stock_code = nt.stock_code
    JOIN theme_grades g ON nt.theme_name = g.theme_name AND p.date = g.date
    JOIN price_data v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    ORDER BY p.stock_code, p.date
    """
    
    print("Connecting to DB and extracting base data...")
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    df = pd.read_sql(query_base, conn)
    
    print("Extracting DWM OHLCV data...")
    query_dwm = """
    SELECT stock_code, d_date, w_open, w_high, w_low, w_close 
    FROM visual.vsl_dwm_ohlcv 
    WHERE d_date >= '2024-10-01'
    """
    dwm_df = pd.read_sql(query_dwm, conn)
    conn.close()
    
    print("Calculating Cycles (V-shape Extrema)...")
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    df['prev_hist'] = df.groupby('stock_code')['histogram'].shift(1)
    df['prev2_hist'] = df.groupby('stock_code')['histogram'].shift(2)
    
    # Point A / C
    df['is_neg_max'] = (df['prev_phase'] == 2) & (df['phase'] == 1) & (df['prev_z'] <= -1.0) & (df['prev2_hist'] > df['prev_hist'])
    # Point B
    df['is_pos_max'] = (df['prev_phase'] == 3) & (df['phase'] == 4) & (df['prev_z'] >= 1.0) & (df['prev2_hist'] < df['prev_hist'])
    
    extrema = df[df['is_neg_max'] | df['is_pos_max']].copy()
    extrema = extrema.sort_values(['stock_code', 'date'])
    extrema['type'] = np.where(extrema['is_neg_max'], -1, 1)
    
    extrema['next_type'] = extrema.groupby('stock_code')['type'].shift(-1)
    extrema['next_date'] = extrema.groupby('stock_code')['date'].shift(-1)
    extrema['next_next_type'] = extrema.groupby('stock_code')['type'].shift(-2)
    extrema['next_next_date'] = extrema.groupby('stock_code')['date'].shift(-2)
    
    valid_seq = extrema[(extrema['type'] == -1) & (extrema['next_type'] == 1) & (extrema['next_next_type'] == -1)].copy()
    valid_seq = valid_seq.dropna(subset=['next_next_date'])
    valid_seq['next_next_date'] = pd.to_datetime(valid_seq['next_next_date']).dt.date
    valid_seq['next_date'] = pd.to_datetime(valid_seq['next_date']).dt.date
    
    # Filter 2025-01-01 onwards
    valid_seq = valid_seq[valid_seq['next_next_date'] >= pd.to_datetime('2025-01-01').date()]
    
    point_a = valid_seq[['stock_code', 'stock_name', 'theme_name', 'date', 'next_date', 'next_next_date']].rename(
        columns={'date': 'date_A', 'next_date': 'date_B', 'next_next_date': 'date_C'}
    )
    
    df['date'] = pd.to_datetime(df['date']).dt.date
    point_c = df[['stock_code', 'theme_name', 'date', 'grade', 'close', 'close_d1', 'close_d2', 'close_d3', 'close_d4', 'close_d5']].rename(
        columns={'date': 'date_C', 'close': 'close_C', 'grade': 'grade_C'}
    )
    
    merged = pd.merge(point_a, point_c, on=['stock_code', 'theme_name', 'date_C'], how='inner')
    
    # Join with weekly data for Point C
    dwm_df['d_date'] = pd.to_datetime(dwm_df['d_date']).dt.date
    target_df = pd.merge(
        merged, dwm_df,
        left_on=['stock_code', 'date_C'], right_on=['stock_code', 'd_date'],
        how='left'
    )
    
    target_df = target_df.dropna(subset=['close_d5', 'w_close'])
    
    # 1. Grade 6 Filter
    target_df = target_df[target_df['grade_C'] == '6등급']
    
    # 2. Candle calculation
    target_df['body'] = np.maximum(abs(target_df['w_close'] - target_df['w_open']), target_df['w_open'] * 0.0001)
    target_df['upper_tail'] = target_df['w_high'] - target_df[['w_open', 'w_close']].max(axis=1)
    target_df['lower_tail'] = target_df[['w_open', 'w_close']].min(axis=1) - target_df['w_low']
    
    # 3. Golden Hammer Filter (Lower >= 3.0, Upper <= 1.0)
    target_df = target_df[(target_df['lower_tail'] / target_df['body'] >= 3.0) & (target_df['upper_tail'] / target_df['body'] <= 1.0)]
    
    print(f"Golden Hammer Cases Found: {len(target_df)}")
    
    # Calculate D+1 to D+5 returns
    for i in range(1, 6):
        target_df[f'd{i}_ret'] = (target_df[f'close_d{i}'] - target_df['close_C']) / target_df['close_C'] * 100
        
    ret_cols = ['d1_ret', 'd2_ret', 'd3_ret', 'd4_ret', 'd5_ret']
    target_df['ret_mean'] = target_df[ret_cols].mean(axis=1)
    target_df['ret_median'] = target_df[ret_cols].median(axis=1)
    
    # Format Raw Data Sheet
    raw_data = target_df[['theme_name', 'stock_name', 'date_A', 'date_B', 'date_C', 
                          'd1_ret', 'd2_ret', 'd3_ret', 'd4_ret', 'd5_ret', 'ret_mean', 'ret_median']].copy()
                          
    raw_data.columns = [
        '테마명', '종목명', 'Point A 일자', 'Point B 일자', 'Point C 일자(매수일)', 
        'D+1 수익률(%)', 'D+2 수익률(%)', 'D+3 수익률(%)', 
        'D+4 수익률(%)', 'D+5 수익률(%)', 'D+1~D+5 수익률 평균(%)', 'D+1~D+5 수익률 중앙값(%)'
    ]
    
    # Summary Statistics
    total_count = len(target_df)
    unique_stocks = target_df['stock_name'].nunique()
    
    all_d5_rets = target_df['d5_ret']
    overall_avg_d5 = all_d5_rets.mean() if total_count > 0 else 0
    overall_med_d5 = all_d5_rets.median() if total_count > 0 else 0
    win_rate = (all_d5_rets > 0).mean() * 100 if total_count > 0 else 0
    
    summary_data = pd.DataFrame([{
        '총 발생 건수': total_count,
        '유니크 종목 수': unique_stocks,
        '전체 데이터 평균 5일 수익률(%)': overall_avg_d5,
        '전체 데이터 중앙값 5일 수익률(%)': overall_med_d5,
        '수익 발생 비율(승률, %)': win_rate
    }])
    
    print("Writing to Excel...")
    out_path = os.path.abspath('scratch/6등급_망치형_수익률분석.xlsx')
    with pd.ExcelWriter(out_path) as writer:
        raw_data.to_excel(writer, sheet_name='Raw Data', index=False)
        summary_data.to_excel(writer, sheet_name='Summary', index=False)
        
    print(f"Excel file created successfully: {out_path}")

if __name__ == "__main__":
    main()
