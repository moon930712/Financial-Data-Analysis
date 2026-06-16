import os
import psycopg2
import pandas as pd

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
    
    print("Extracting Theme Grades...")
    import warnings
    warnings.filterwarnings('ignore')
    df_themes = pd.read_sql(query_themes, conn)
    conn.close()
    
    print("Finding 6 -> 1 -> 6 cycles for each theme...")
    results = []
    
    for theme, group in df_themes.groupby('theme_name'):
        group = group.sort_values('date')
        dates = group['date'].tolist()
        grades = group['grade'].tolist()
        cnts = group['total_cnt'].tolist()
        
        cycles = []
        state = 0
        last_6_idx = -1
        first_1_idx = -1
        
        for i in range(len(grades)):
            g = grades[i]
            
            if state == 0:
                if g == '6등급':
                    last_6_idx = i
                elif last_6_idx != -1:
                    state = 1
                    if g == '1등급':
                        first_1_idx = i
                        state = 2
            elif state == 1:
                if g == '6등급':
                    last_6_idx = i
                    state = 0
                elif g == '1등급':
                    first_1_idx = i
                    state = 2
            elif state == 2:
                if g == '6등급':
                    end_6_idx = i
                    cycles.append((last_6_idx, first_1_idx, end_6_idx))
                    last_6_idx = i
                    state = 0
                    
        if cycles:
            best_cycle = cycles[-1] # 가장 최근 사이클
            start_idx, mid_idx, end_idx = best_cycle
            
            start_date = dates[start_idx]
            mid_date = dates[mid_idx]
            end_date = dates[end_idx]
            
            period_grades = grades[start_idx : end_idx + 1]
            trend_str = " -> ".join(period_grades)
            
            total_cnt = cnts[start_idx]
            duration = end_idx - start_idx
            
            results.append({
                '테마명': theme,
                '종목수': total_cnt,
                '6등급 날짜': start_date.strftime('%Y-%m-%d'),
                '1등급날짜': mid_date.strftime('%Y-%m-%d'),
                '6등급날짜': end_date.strftime('%Y-%m-%d'),
                '총기간': f"{duration}영업일",
                '등급변화 추이': trend_str
            })
            
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        print("조건을 만족하는 사이클이 없습니다.")
        return
        
    df_res = df_res.sort_values('6등급날짜', ascending=False)
    
    out_path = os.path.abspath('scratch/analyze_theme_cycle_6_1_6.xlsx')
    with pd.ExcelWriter(out_path) as writer:
        df_res.to_excel(writer, sheet_name='Cycles', index=False)
        
    print(f"\\n완료! 결과가 {out_path} 에 저장되었습니다.")
    print("\\n=== 상위 5개 결과 미리보기 ===")
    print(df_res.head(5).to_string(index=False))

if __name__ == "__main__":
    main()
