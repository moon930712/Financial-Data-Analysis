import os
import psycopg2
import pandas as pd
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
    query = """
    WITH target_date AS (
        SELECT MAX(date) AS dt FROM visual.vsl_anly_stocks_price_subindex02
    )
    , all_valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date <= (SELECT dt FROM target_date)
          AND date >= '2025-11-01'
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
    , trade_rank_calc AS (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY date ORDER BY avg_trade_value DESC NULLS LAST) AS trade_value_rank
        FROM theme_aggregation
    )
    , final_ranking AS (
        SELECT date, theme_name
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                total_cnt DESC
              ) AS global_rank
        FROM trade_rank_calc
        WHERE trade_value_rank <= 150
    )
    , date_theme_ranks AS (
        SELECT 
            date
            , theme_name
            , global_rank as rank_d0
            , LAG(global_rank, 1) OVER(PARTITION BY theme_name ORDER BY date) as rank_d1
            , LAG(global_rank, 2) OVER(PARTITION BY theme_name ORDER BY date) as rank_d2
            , LAG(global_rank, 3) OVER(PARTITION BY theme_name ORDER BY date) as rank_d3
        FROM final_ranking
    )
    , theme_grades AS (
        SELECT 
            date
            , theme_name
            , rank_d0
            , CASE WHEN rank_d3 <= 25 THEN '1등급' WHEN rank_d3 <= 50 THEN '2등급' WHEN rank_d3 <= 75 THEN '3등급' WHEN rank_d3 <= 100 THEN '4등급' WHEN rank_d3 <= 125 THEN '5등급' WHEN rank_d3 IS NULL THEN 'Unknown' ELSE '6등급' END AS grade_d3
            , CASE WHEN rank_d2 <= 25 THEN '1등급' WHEN rank_d2 <= 50 THEN '2등급' WHEN rank_d2 <= 75 THEN '3등급' WHEN rank_d2 <= 100 THEN '4등급' WHEN rank_d2 <= 125 THEN '5등급' ELSE '6등급' END
              || ' -> ' ||
              CASE WHEN rank_d1 <= 25 THEN '1등급' WHEN rank_d1 <= 50 THEN '2등급' WHEN rank_d1 <= 75 THEN '3등급' WHEN rank_d1 <= 100 THEN '4등급' WHEN rank_d1 <= 125 THEN '5등급' ELSE '6등급' END
              || ' -> ' ||
              CASE WHEN rank_d0 <= 25 THEN '1등급' WHEN rank_d0 <= 50 THEN '2등급' WHEN rank_d0 <= 75 THEN '3등급' WHEN rank_d0 <= 100 THEN '4등급' WHEN rank_d0 <= 125 THEN '5등급' ELSE '6등급' END
              AS pattern
        FROM date_theme_ranks
        WHERE rank_d0 <= 20
          AND date >= '2026-01-01'
    )
    , target_themes AS (
        SELECT date, theme_name, pattern, grade_d3
        FROM theme_grades
        WHERE pattern IN (
            '6등급 -> 4등급 -> 1등급',
            '4등급 -> 3등급 -> 1등급',
            '3등급 -> 2등급 -> 1등급'
        )
    )
    , stock_indicators AS (
        SELECT 
            v1.date, v1.stock_code, v1.open, v1.close, v1.trade_value,
            v2.rsi, (v1.close / NULLIF(v1.ma20, 0)) * 100 AS disparity_20,
            (v1.trade_value / NULLIF(AVG(v1.trade_value) OVER(PARTITION BY v1.stock_code ORDER BY v1.date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING), 0)) AS volume_spike
        FROM visual.vsl_anly_stocks_price_subindex01 v1
        JOIN visual.vsl_anly_stocks_price_subindex02 v2 ON v1.stock_code = v2.stock_code AND v1.date = v2.date
        WHERE v1.date IN (SELECT date FROM all_valid_dates)
    )
    , daily_sm AS (
        SELECT date, stock_code, SUM(CASE WHEN investor IN ('기관합계', '외국인') THEN net_trade_vol ELSE 0 END) as daily_sm_flow
        FROM visual.vsl_krx_stocks_investor_shares_trading_info
        WHERE date IN (SELECT date FROM all_valid_dates)
        GROUP BY date, stock_code
    )
    , smart_money AS (
        SELECT date, stock_code, SUM(daily_sm_flow) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as sm_flow
        FROM daily_sm
    )
    SELECT 
        tt.pattern
        , tt.grade_d3
        , COUNT(*) as cnt
    FROM target_themes tt
    JOIN industry.theme_name_list nl ON tt.theme_name = nl.theme_name
    JOIN theme_phase_classification tpc ON nl.stock_code = tpc.stock_code AND tpc.date = tt.date
    JOIN stock_indicators ts ON nl.stock_code = ts.stock_code AND ts.date = tt.date
    JOIN smart_money sm ON nl.stock_code = sm.stock_code AND sm.date = tt.date
    WHERE tpc.phase IN (1, 3)
      AND ts.volume_spike >= 1.8
      AND COALESCE(sm.sm_flow, 0) >= 130000
      AND ts.disparity_20 <= 120
      AND ts.rsi >= 30
      AND ts.rsi <= 70
    GROUP BY tt.pattern, tt.grade_d3
    ORDER BY tt.pattern, cnt DESC;
    """

    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    print("Executing Day-3 distribution query...")
    df = pd.read_sql(query, conn)
    conn.close()
    
    if len(df) > 0:
        patterns = df['pattern'].unique()
        for p in patterns:
            print(f"\n=== [{p}] 패턴의 직전일(Day-3) 등급 분포 ===")
            sub_df = df[df['pattern'] == p]
            total = sub_df['cnt'].sum()
            for _, row in sub_df.iterrows():
                print(f"  {row['grade_d3']}: {row['cnt']}건 ({row['cnt']/total*100:.1f}%)")
    else:
        print("추출된 데이터가 없습니다.")

if __name__ == "__main__":
    main()
