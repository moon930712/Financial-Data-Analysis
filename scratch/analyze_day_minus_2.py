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
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    query = """
    WITH all_valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2023-01-01' -- 백테스트 기간 (최근 약 1.5년)
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
            , COALESCE(SUM(v1.trade_value), 0) / COUNT(*) AS avg_trade_value
        FROM industry.theme_name_list nt
        INNER JOIN theme_phase_classification p ON nt.stock_code = p.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
        WHERE v1.close > 1000 
        GROUP BY nt.theme_name, p.date
        HAVING COUNT(*) >= 5
    )
    , final_ranking AS (
        SELECT date, theme_name
            , total_cnt, phase1_cnt, phase2_cnt, phase3_cnt, phase4_cnt, avg_trade_value
            , LAG(avg_trade_value, 1) OVER(PARTITION BY theme_name ORDER BY date) as lag_avg_trade_value
            , LAG(phase1_cnt, 1) OVER(PARTITION BY theme_name ORDER BY date) as lag_phase1_cnt
            , LAG(phase3_cnt, 1) OVER(PARTITION BY theme_name ORDER BY date) as lag_phase3_cnt
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                total_cnt DESC
              ) AS global_rank
        FROM theme_aggregation
    )
    , theme_grades AS (
        SELECT 
            date
            , theme_name
            , total_cnt, phase1_cnt, phase2_cnt, phase3_cnt, phase4_cnt
            , avg_trade_value, lag_avg_trade_value
            , phase1_cnt - lag_phase1_cnt as phase1_increase
            , phase3_cnt - lag_phase3_cnt as phase3_increase
            , CASE WHEN lag_avg_trade_value > 0 THEN avg_trade_value / lag_avg_trade_value ELSE 1 END as trade_value_spike
            , global_rank
            , CASE 
                WHEN global_rank <= 25 THEN '1등급' 
                WHEN global_rank <= 50 THEN '2등급' 
                WHEN global_rank <= 75 THEN '3등급' 
                WHEN global_rank <= 100 THEN '4등급' 
                WHEN global_rank <= 125 THEN '5등급' 
                ELSE '6등급' 
              END AS grade
            , LEAD(CASE 
                WHEN global_rank <= 25 THEN '1등급' 
                WHEN global_rank <= 50 THEN '2등급' 
                WHEN global_rank <= 75 THEN '3등급' 
                WHEN global_rank <= 100 THEN '4등급' 
                WHEN global_rank <= 125 THEN '5등급' 
                ELSE '6등급' 
              END, 1) OVER(PARTITION BY theme_name ORDER BY date) as future_grade_d1
            , LEAD(CASE 
                WHEN global_rank <= 25 THEN '1등급' 
                WHEN global_rank <= 50 THEN '2등급' 
                WHEN global_rank <= 75 THEN '3등급' 
                WHEN global_rank <= 100 THEN '4등급' 
                WHEN global_rank <= 125 THEN '5등급' 
                ELSE '6등급' 
              END, 2) OVER(PARTITION BY theme_name ORDER BY date) as future_grade_d2
        FROM final_ranking
    )
    SELECT * 
    FROM theme_grades
    WHERE grade IN ('6등급', '4등급', '3등급')
      AND future_grade_d2 IS NOT NULL
      AND date >= '2023-02-01' -- 앞부분 1달은 이동평균 및 랙 계산용으로 뺌
    """
    
    print("Fetching theme base data from DB...")
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"Total rows fetched: {len(df)}")
    
    def analyze_grade(grade_name):
        df_g = df[df['grade'] == grade_name].copy()
        
        # 특정 패턴인 경우만 Success로 볼 수도 있지만, 최종적으로 Day+2에 1등급에 안착했는지를 Success로 정의
        df_g['is_success'] = (df_g['future_grade_d2'] == '1등급')
        
        # 추가로 Day+1의 조건도 볼 수 있음. 
        # 예: 6등급 -> 4등급 -> 1등급 패턴 타겟 시, Day+1이 4등급이어야 완벽한 성공이지만, 일단 D+2 1등급을 큰 범주의 성공으로 둠.
        
        succ_cnt = df_g['is_success'].sum()
        fail_cnt = (~df_g['is_success']).sum()
        
        print(f"\n=== {grade_name} -> Day+2 1등급 도달 분석 ===")
        print(f"Total {grade_name} cases: {len(df_g)}")
        print(f"Success cases (reached 1등급): {succ_cnt} ({succ_cnt/len(df_g)*100:.2f}%)")
        print(f"Failure cases: {fail_cnt} ({fail_cnt/len(df_g)*100:.2f}%)")
        
        if succ_cnt > 0:
            succ_df = df_g[df_g['is_success']]
            fail_df = df_g[~df_g['is_success']]
            
            features = ['trade_value_spike', 'phase1_increase', 'phase3_increase', 'phase1_cnt', 'avg_trade_value']
            
            print("\n[평균값 비교 (Success vs Failure)]")
            for f in features:
                s_mean = succ_df[f].mean()
                f_mean = fail_df[f].mean()
                diff = s_mean - f_mean
                print(f"  - {f}: Success = {s_mean:.2f} / Failure = {f_mean:.2f} (Diff: {diff:.2f})")
                
            print("\n[상위 25% (75th Percentile) 비교]")
            for f in features:
                s_75 = succ_df[f].quantile(0.75)
                f_75 = fail_df[f].quantile(0.75)
                print(f"  - {f}: Success = {s_75:.2f} / Failure = {f_75:.2f}")

    analyze_grade('6등급')
    analyze_grade('4등급')
    analyze_grade('3등급')

    out_file = 'scratch/day_minus_2_raw.csv'
    df.to_csv(out_file, index=False, encoding='utf-8-sig')
    print(f"\nData saved to {out_file}")

if __name__ == "__main__":
    main()
