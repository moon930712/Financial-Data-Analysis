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
    # To check the hypothesis, we will run the query without the final WHERE date filter
    # And we will extract all rows for '조선기자재'
    
    query = """
    WITH histo_base AS (
        SELECT 
            m.date
            , m.stock_code
            , m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
    )
    , phase_classification AS (
        SELECT 
            date
            , stock_code
            , stock_name
            , CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN 1 
                WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 
                WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 
                ELSE 4
              END as phase
        FROM histo_base
        WHERE date BETWEEN '2026-03-06'::date - 7 AND '2026-03-06'::date
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
        JOIN phase_classification p ON nt.stock_code = p.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 
            ON p.stock_code = v1.stock_code AND p.date = v1.date
        WHERE v1.close > 1000 
        GROUP BY nt.theme_name, p.date
        HAVING COUNT(*) >= 5 
    )
    , ratio_calculation AS (
        SELECT 
            *
            , ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) as weighted_score
            , ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) as phase1_ratio
            , ROUND((phase2_cnt::numeric / total_cnt) * 100, 2) as phase2_ratio
            , ROUND((phase3_cnt::numeric / total_cnt) * 100, 2) as phase3_ratio
            , ROUND((phase4_cnt::numeric / total_cnt) * 100, 2) as phase4_ratio
        FROM theme_aggregation
    )
    , final_ratio AS (
        SELECT
            *
            , ROUND(((phase1_cnt + phase3_cnt)::numeric / total_cnt) * 100, 2) as g1_ratio
            , ROUND(((phase2_cnt + phase4_cnt)::numeric / total_cnt) * -100, 2) as g2_ratio
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY avg_trade_value DESC NULLS LAST) as trade_value_rank
        FROM ratio_calculation
    )
    , final_ranking AS (
        SELECT 
            date
            , to_char(date, 'YYYY-MM-DD') as date_str
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY weighted_score DESC, phase1_ratio DESC, total_cnt DESC) as global_rank
            , COUNT(*) OVER(PARTITION BY date) as total_themes_cnt
            , theme_name
            , total_cnt
            , phase1_cnt
            , phase1_ratio
            , phase2_ratio
            , phase3_ratio
            , phase4_ratio
            , weighted_score
            , g1_ratio
            , g2_ratio
            , avg_trade_value
            , trade_value_rank
        FROM final_ratio
        -- WE TEMPORARILY COMMENT OUT THE FILTER TO SEE WHAT HAPPENED ON 03-05
        -- WHERE trade_value_rank <= 150 
    )
    , rank_tracking AS (
        SELECT
            *
            , LAG(global_rank, 1) OVER(PARTITION BY theme_name ORDER BY date) as prev_rank
        FROM final_ranking
    )
    SELECT *
    FROM rank_tracking
    WHERE theme_name = '조선기자재'
    ORDER BY date;
    """
    
    print("Connecting to DB...")
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("\n[조선기자재]의 최근 7일간 전체 데이터 (필터 제거 버전):")
    pd.set_option('display.max_columns', None)
    print(df[['date_str', 'theme_name', 'trade_value_rank', 'global_rank', 'prev_rank']].to_string(index=False))

if __name__ == "__main__":
    main()
