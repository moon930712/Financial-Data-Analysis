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
        p.date, p.stock_code, nt.theme_name, g.grade,
        p.histogram, p.phase,
        v1.close, v1.close_d5
    FROM theme_phase_classification p
    JOIN industry.theme_name_list nt ON p.stock_code = nt.stock_code
    LEFT JOIN theme_grades g ON nt.theme_name = g.theme_name AND p.date = g.date
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
    SELECT stock_code, d_date, d_volume, d_open, d_high, d_low, d_close, d_ma20, w_open, w_high, w_low, w_close 
    FROM visual.vsl_dwm_ohlcv 
    WHERE d_date >= '2024-06-01'
    """
    dwm_df = pd.read_sql(query_dwm, conn)
    conn.close()
    
    print("Calculating Cycles and MACD Depths...")
    df['hist_mean'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df['hist_std'] = df.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df['z_score'] = (df['histogram'] - df['hist_mean']) / df['hist_std']
    
    df['prev_phase'] = df.groupby('stock_code')['phase'].shift(1)
    df['prev_z'] = df.groupby('stock_code')['z_score'].shift(1)
    df['prev_hist'] = df.groupby('stock_code')['histogram'].shift(1)
    df['prev2_hist'] = df.groupby('stock_code')['histogram'].shift(2)
    
    df['valley_depth'] = df['prev_hist'].abs()
    
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
    
    valid_seq['date_A'] = pd.to_datetime(valid_seq['date'])
    valid_seq['date_B'] = pd.to_datetime(valid_seq['next_date'])
    valid_seq['date_C'] = pd.to_datetime(valid_seq['next_next_date'])
    valid_seq = valid_seq[valid_seq['date_C'] >= pd.to_datetime('2025-01-01')]
    
    df['date'] = pd.to_datetime(df['date'])
    lookup_df = df.set_index(['stock_code', 'date'])
    
    def get_features(row):
        try:
            a_data = lookup_df.loc[(row['stock_code'], row['date_A'])]
            c_data = lookup_df.loc[(row['stock_code'], row['date_C'])]
            
            if isinstance(a_data, pd.DataFrame): a_data = a_data.iloc[0]
            if isinstance(c_data, pd.DataFrame): c_data = c_data.iloc[0]
            
            return pd.Series({
                'price_A': float(a_data['close']),
                'macd_depth_A': float(a_data['valley_depth']),
                'price_C': float(c_data['close']),
                'macd_depth_C': float(c_data['valley_depth']),
                'ret_5d': float((c_data['close_d5'] - c_data['close']) / c_data['close'] * 100),
                'grade_C': c_data['grade']
            })
        except Exception as e:
            return pd.Series({ 'price_A': np.nan, 'macd_depth_A': np.nan, 'price_C': np.nan, 'macd_depth_C': np.nan, 'ret_5d': np.nan, 'grade_C': None })

    features = valid_seq.apply(get_features, axis=1)
    valid_seq = pd.concat([valid_seq, features], axis=1)
    valid_seq = valid_seq.dropna(subset=['price_A', 'price_C', 'macd_depth_A', 'macd_depth_C', 'ret_5d'])
    
    # Isolate "④ 완벽한 지하실" Quadrant (Lower Low + MACD Deepens)
    abyss_df = valid_seq[(valid_seq['price_C'] < valid_seq['price_A']) & (valid_seq['macd_depth_C'] >= valid_seq['macd_depth_A'])].copy()
    
    # Merge with DWM to get volume and candles
    abyss_df['date_C_only'] = abyss_df['date_C'].dt.date
    dwm_df['d_date'] = pd.to_datetime(dwm_df['d_date']).dt.date
    
    merged = pd.merge(abyss_df, dwm_df, left_on=['stock_code', 'date_C_only'], right_on=['stock_code', 'd_date'], how='inner')
    
    # Calculate factors
    merged['price_drop_pct'] = (merged['price_C'] - merged['price_A']) / merged['price_A'] * 100
    merged['vol_ratio'] = merged['d_volume'] / np.maximum(merged['d_volume'].rolling(20, min_periods=1).mean(), 1) # Note: we actually have d_ma20 for volume? Wait, d_ma20 is price MA. We need volume MA. I'll approximate or just use w_avg_volume if needed. Wait, dwm_df has w_avg_volume? I didn't select it. I will calculate rolling here.
    # Actually, dwm_df isn't sorted to do rolling easily. I'll just use a proxy or fetch w_avg_volume.
    # Let's approximate: Vol Ratio isn't perfectly 20MA here but we can check if it's < 1.0 (very low) by sorting dwm_df.
    # A better way is to do it on dwm_df before merge.
    dwm_df = dwm_df.sort_values(['stock_code', 'd_date'])
    dwm_df['vol_20ma'] = dwm_df.groupby('stock_code')['d_volume'].transform(lambda x: x.rolling(20, min_periods=5).mean())
    
    merged = pd.merge(abyss_df, dwm_df, left_on=['stock_code', 'date_C_only'], right_on=['stock_code', 'd_date'], how='inner')
    merged['vol_ratio'] = merged['d_volume'] / np.maximum(merged['vol_20ma'], 1)
    
    # Candle and Buying Pressure
    merged['body'] = np.maximum(abs(merged['w_close'] - merged['w_open']), merged['w_open'] * 0.0001)
    merged['lower_tail'] = merged[['w_open', 'w_close']].min(axis=1) - merged['w_low']
    merged['is_golden_hammer'] = (merged['lower_tail'] / merged['body'] >= 3.0)
    
    merged['d_buy_pressure'] = np.where(merged['d_high'] > merged['d_low'], 
                                       (merged['d_close'] - merged['d_low']) / (merged['d_high'] - merged['d_low']) * 100, 
                                       50)
                                       
    win_group = merged[merged['ret_5d'] > 0]
    loss_group = merged[merged['ret_5d'] <= 0]
    
    print(f"\n========================================================")
    print(f"📉 [④ 완벽한 지하실] 수익(Win) vs 손실(Loss) 종목 집중 분석")
    print(f"========================================================\n")
    print(f"총 분석 건수: {len(merged)}건 (수익: {len(win_group)}건 / 손실: {len(loss_group)}건)")
    
    def print_stats(group_df, name):
        if len(group_df) == 0: return
        
        grade_6_pct = (group_df['grade_C'] == '6등급').mean() * 100
        hammer_pct = group_df['is_golden_hammer'].mean() * 100
        avg_vol_ratio = group_df['vol_ratio'].mean()
        extreme_low_vol_pct = (group_df['vol_ratio'] <= 0.7).mean() * 100
        avg_buy_pressure = group_df['d_buy_pressure'].mean()
        avg_drop = group_df['price_drop_pct'].mean()
        
        print(f"\n🟢 [{name} 그룹]")
        print(f"  1. 테마 소외도 (6등급 비율): {grade_6_pct:.1f}%")
        print(f"  2. 세력 개입 (황금 망치형 출현율): {hammer_pct:.1f}%")
        print(f"  3. 당일 매수 강도 (종가가 고가에 얼마나 꽉 찼는가): {avg_buy_pressure:.1f}%")
        print(f"  4. 매도세 소멸 (당일 거래량이 20일 평균의 0.7배 이하인 비율): {extreme_low_vol_pct:.1f}% (평균 거래량 배수: {avg_vol_ratio:.2f}x)")
        print(f"  5. 지하실 깊이 (Point A 대비 하락폭): {avg_drop:.1f}%")

    print_stats(win_group, "수익(Win) - 5일 뒤 상승한 종목들")
    print_stats(loss_group, "손실(Loss) - 계속 지하실을 파고 내려간 종목들")

if __name__ == "__main__":
    main()
