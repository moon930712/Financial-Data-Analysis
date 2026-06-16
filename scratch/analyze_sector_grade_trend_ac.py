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
    print("Connecting to DB...")
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # Query 1: Get daily theme grades
    query_themes = """
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
            date, stock_code,
            CASE 
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
        SELECT date, theme_name, total_cnt
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                total_cnt DESC
              ) AS global_rank
        FROM theme_aggregation
    )
    SELECT 
        date, theme_name, total_cnt
        , CASE 
            WHEN global_rank <= 25 THEN '1등급' 
            WHEN global_rank <= 50 THEN '2등급' 
            WHEN global_rank <= 75 THEN '3등급' 
            WHEN global_rank <= 100 THEN '4등급' 
            WHEN global_rank <= 125 THEN '5등급' 
            ELSE '6등급' 
          END AS grade
    FROM final_ranking
    ORDER BY theme_name, date
    """
    
    # Query 2: Get all stocks' phases and z-scores
    query_stocks = """
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
    SELECT 
        p.date, p.stock_code, nt.theme_name, nt.stock_name,
        p.histogram,
        CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1 
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 
            ELSE 4 
        END as phase
    FROM theme_histo_base p
    JOIN industry.theme_name_list nt ON p.stock_code = nt.stock_code
    ORDER BY p.stock_code, p.date
    """
    
    print("Extracting Theme Grades...")
    df_themes = pd.read_sql(query_themes, conn)
    
    print("Extracting Stock Phases...")
    df_stocks = pd.read_sql(query_stocks, conn)
    
    conn.close()
    
    print("Calculating Z-scores and Cycles for stocks...")
    df_stocks['hist_mean'] = df_stocks.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).mean())
    df_stocks['hist_std'] = df_stocks.groupby('stock_code')['histogram'].transform(lambda x: x.rolling(60, min_periods=20).std())
    df_stocks['z_score'] = (df_stocks['histogram'] - df_stocks['hist_mean']) / df_stocks['hist_std']
    
    df_stocks['prev_phase'] = df_stocks.groupby('stock_code')['phase'].shift(1)
    df_stocks['prev_z'] = df_stocks.groupby('stock_code')['z_score'].shift(1)
    df_stocks['prev_hist'] = df_stocks.groupby('stock_code')['histogram'].shift(1)
    df_stocks['prev2_hist'] = df_stocks.groupby('stock_code')['histogram'].shift(2)
    
    # Point A / C (Neg Max)
    df_stocks['is_neg_max'] = (
        (df_stocks['prev_phase'] == 2) & 
        (df_stocks['phase'] == 1) & 
        (df_stocks['prev_z'] <= -1.0) &
        (df_stocks['prev2_hist'] > df_stocks['prev_hist'])
    )
    
    # Point B (Pos Max)
    df_stocks['is_pos_max'] = (
        (df_stocks['prev_phase'] == 3) & 
        (df_stocks['phase'] == 4) & 
        (df_stocks['prev_z'] >= 1.0) &
        (df_stocks['prev2_hist'] < df_stocks['prev_hist'])
    )
    
    extrema = df_stocks[df_stocks['is_neg_max'] | df_stocks['is_pos_max']].copy()
    extrema = extrema.sort_values(['stock_code', 'date'])
    extrema['type'] = np.where(extrema['is_neg_max'], -1, 1)
    
    extrema['next_type'] = extrema.groupby('stock_code')['type'].shift(-1)
    extrema['next_date'] = extrema.groupby('stock_code')['date'].shift(-1)
    extrema['next_next_type'] = extrema.groupby('stock_code')['type'].shift(-2)
    extrema['next_next_date'] = extrema.groupby('stock_code')['date'].shift(-2)
    
    valid_seq = extrema[(extrema['type'] == -1) & (extrema['next_type'] == 1) & (extrema['next_next_type'] == -1)].copy()
    valid_seq = valid_seq.dropna(subset=['next_next_date'])
    
    valid_seq['date'] = pd.to_datetime(valid_seq['date'])
    valid_seq['next_date'] = pd.to_datetime(valid_seq['next_date'])
    valid_seq['next_next_date'] = pd.to_datetime(valid_seq['next_next_date'])
    
    # Filter for Point C >= 2026-01-01
    valid_seq = valid_seq[valid_seq['next_next_date'] >= pd.to_datetime('2026-01-01')]
    
    valid_seq = valid_seq.rename(columns={'date': 'date_A', 'next_date': 'date_B', 'next_next_date': 'date_C'})
    
    df_themes['date'] = pd.to_datetime(df_themes['date'])
    theme_grades_dict = {}
    for _, row in df_themes.iterrows():
        theme = row['theme_name']
        dt = row['date']
        if theme not in theme_grades_dict:
            theme_grades_dict[theme] = {}
        theme_grades_dict[theme][dt] = {'grade': row['grade'], 'total_cnt': row['total_cnt']}
    
    print("Tracing Sector Grade Trends...")
    results = []
    
    all_dates = sorted(df_themes['date'].unique())
    
    for _, row in valid_seq.iterrows():
        theme = row['theme_name']
        stock = row['stock_name']
        date_a = row['date_A']
        date_b = row['date_B']
        date_c = row['date_C']
        
        if theme not in theme_grades_dict: continue
        if date_a not in theme_grades_dict[theme]: continue
        
        grade_a = theme_grades_dict[theme][date_a]['grade']
        total_cnt_a = theme_grades_dict[theme][date_a]['total_cnt']
        
        if grade_a == '6등급':
            # Track from A to C
            trend = []
            valid_period = [d for d in all_dates if date_a <= d <= date_c]
            for d in valid_period:
                if d in theme_grades_dict[theme]:
                    trend.append(theme_grades_dict[theme][d]['grade'])
            
            trend_str = " -> ".join(trend)
            results.append({
                '섹터명': theme,
                '섹터 전체 종목수': total_cnt_a,
                '종목명': stock,
                'Point_A': date_a.strftime('%Y-%m-%d'),
                'Point_B': date_b.strftime('%Y-%m-%d'),
                'Point_C': date_c.strftime('%Y-%m-%d'),
                'Point_A_섹터_등급': grade_a,
                '등급변화추이': trend_str
            })
            
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        print("조건을 만족하는 데이터가 없습니다.")
        return
        
    grouped = df_res.groupby(['섹터명', '섹터 전체 종목수', 'Point_A', 'Point_B', 'Point_C', 'Point_A_섹터_등급', '등급변화추이']).agg(
        사이클_통과_종목수=('종목명', 'count'),
        통과_종목명=('종목명', lambda x: ', '.join(x))
    ).reset_index()
    
    grouped = grouped.rename(columns={
        'Point_A': 'Point A 날짜',
        'Point_B': 'Point B 날짜',
        'Point_C': 'Point C 날짜',
        'Point_A_섹터_등급': 'Point A 당일 섹터 등급',
        '등급변화추이': '등급 변화추이 (A~C 매일)',
        '사이클_통과_종목수': '사이클 통과 종목수',
        '통과_종목명': '통과 종목명'
    })
    
    final_cols = [
        '섹터명', '섹터 전체 종목수', '사이클 통과 종목수', '통과 종목명',
        'Point A 날짜', 'Point B 날짜', 'Point C 날짜', 'Point A 당일 섹터 등급', '등급 변화추이 (A~C 매일)'
    ]
    grouped = grouped[final_cols]
    
    grouped = grouped.sort_values(['Point C 날짜', '섹터명'], ascending=[False, True])
    
    out_path = os.path.abspath('scratch/analyze_sector_grade_trend_ac.xlsx')
    with pd.ExcelWriter(out_path) as writer:
        grouped.to_excel(writer, sheet_name='Summary', index=False)
        df_res.to_excel(writer, sheet_name='Raw Data (Per Stock)', index=False)
        
    print(f"\n완료! 결과가 {out_path} 에 저장되었습니다.")
    print("\n=== 상위 5개 결과 미리보기 ===")
    print(grouped.head(5).to_string(index=False))

if __name__ == "__main__":
    main()
