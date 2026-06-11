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
            LEAD(close, 5) OVER(PARTITION BY stock_code ORDER BY date) as close_d5
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '2023-10-01'
    )
    SELECT 
        p.date, p.stock_code, nt.stock_name, nt.theme_name, g.grade,
        p.histogram, p.phase,
        v1.close, v1.close_d5
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
    
    # Query DWM table for 2025 onwards
    print("Extracting DWM OHLCV and MA data...")
    query_dwm = """
    SELECT stock_code, d_date, d_ma5, d_ma10, d_ma20, w_open, w_high, w_low, w_close 
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
    
    # V-shape Extrema
    df['is_neg_max'] = (df['prev_phase'] == 2) & (df['phase'] == 1) & (df['prev_z'] <= -1.0) & (df['prev2_hist'] > df['prev_hist'])
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
    
    # Filter for 2025-01-01 onwards
    valid_seq = valid_seq[valid_seq['next_next_date'] >= pd.to_datetime('2025-01-01').date()]
    
    print(f"Found {len(valid_seq)} valid cycles since 2025-01-01.")
    
    point_c = df[['stock_code', 'date', 'grade', 'close', 'close_d5']].copy()
    point_c['date'] = pd.to_datetime(point_c['date']).dt.date
    
    target_df = pd.merge(
        valid_seq[['stock_code', 'stock_name', 'next_next_date']],
        point_c,
        left_on=['stock_code', 'next_next_date'], right_on=['stock_code', 'date'],
        how='inner'
    )
    
    # Merge with DWM data
    dwm_df['d_date'] = pd.to_datetime(dwm_df['d_date']).dt.date
    target_df = pd.merge(
        target_df, dwm_df,
        left_on=['stock_code', 'date'], right_on=['stock_code', 'd_date'],
        how='left'
    )
    
    # Calculate return and drop NaNs
    target_df['ret_5d'] = (target_df['close_d5'] - target_df['close']) / target_df['close'] * 100
    target_df = target_df.dropna(subset=['ret_5d', 'w_close'])
    
    # Split into Win / Loss
    win_group = target_df[target_df['ret_5d'] > 0].copy()
    loss_group = target_df[target_df['ret_5d'] <= 0].copy()
    
    print("================================================================")
    print(f"🔥 [분석 대상]: 2025년 이후 Point C 진입 종목 (테마등급, 하락률 조건 무관)")
    print(f"🔥 [총 케이스 수]: {len(target_df)}건 (수익 {len(win_group)}건 / 손실 {len(loss_group)}건)")
    print("================================================================\n")
    
    def analyze_group(group_df, name):
        total = len(group_df)
        if total == 0: return
        
        print(f"🟢 [{name} 그룹 분석] - 총 {total}건")
        
        # 1. Grade Distribution
        grade_dist = group_df['grade'].value_counts(normalize=True).sort_index() * 100
        print("  [1] 테마 등급 분포:")
        for grade, pct in grade_dist.items():
            print(f"      - {grade}: {pct:.1f}%")
            
        # 2. Moving Average Alignment
        group_df['ma_align'] = np.where(
            (group_df['d_ma5'] > group_df['d_ma10']) & (group_df['d_ma10'] > group_df['d_ma20']), '정배열',
            np.where((group_df['d_ma5'] < group_df['d_ma10']) & (group_df['d_ma10'] < group_df['d_ma20']), '역배열', '혼조세')
        )
        ma_dist = group_df['ma_align'].value_counts(normalize=True) * 100
        print("  [2] 일봉 이평선 배열 (5/10/20):")
        for align, pct in ma_dist.items():
            print(f"      - {align}: {pct:.1f}%")
            
        # 3. Weekly Candle Shape
        group_df['candle_color'] = np.where(group_df['w_close'] >= group_df['w_open'], '양봉', '음봉')
        
        body_len = abs(group_df['w_close'] - group_df['w_open'])
        upper_tail = group_df['w_high'] - group_df[['w_open', 'w_close']].max(axis=1)
        lower_tail = group_df[['w_open', 'w_close']].min(axis=1) - group_df['w_low']
        
        # 꼬리 판단 (몸통의 2배 이상이면 꼬리로 인정)
        group_df['shape'] = '일반'
        group_df.loc[lower_tail >= body_len * 2, 'shape'] = '망치형(밑꼬리)'
        group_df.loc[upper_tail >= body_len * 2, 'shape'] = '역망치형(윗꼬리)'
        group_df.loc[(lower_tail >= body_len * 2) & (upper_tail >= body_len * 2), 'shape'] = '도지/팽이형(위아래꼬리)'
        
        candle_dist = (group_df['candle_color'] + ' - ' + group_df['shape']).value_counts(normalize=True) * 100
        print("  [3] 주봉 캔들 형태 (Point C 속한 주간):")
        for candle, pct in candle_dist.items():
            print(f"      - {candle}: {pct:.1f}%")
        print("\n")
        
    analyze_group(win_group, "수익(Win)")
    analyze_group(loss_group, "손실(Loss)")

if __name__ == "__main__":
    main()
