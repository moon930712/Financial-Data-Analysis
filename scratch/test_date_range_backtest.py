import os
import psycopg2
import pandas as pd

def load_env(filepath):
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('.env')

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

try:
    query = """
    WITH histo_base AS (
        SELECT 
            m.date
            , m.stock_code
            , m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
    ),
    phase_classification AS (
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
        WHERE date >= '2026-03-30'::date AND date <= current_date
    )
    , theme_aggregation AS (
        SELECT 
            nt.theme_name
            , p.date
            , COUNT(*) as total_cnt
            , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
            , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt
            , SUM(v1.trade_value) / COUNT(*) AS avg_trade_value
        FROM industry.theme_name_list nt 
        JOIN phase_classification p ON nt.stock_code = p.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 
            ON p.stock_code = v1.stock_code AND p.date = v1.date
        WHERE 1 = 1
            AND nt.theme_name NOT IN ('테마없음', 'ETF', 'ETN')
            AND nt.theme_name NOT LIKE '%스팩%'
            AND nt.theme_name NOT LIKE '%그룹%'
        GROUP BY nt.theme_name, p.date
        HAVING COUNT(*) >= 5 
    )
    , final_ratio AS (
        SELECT
            *,
            ROUND(((phase1_cnt::numeric * 1.5 + phase3_cnt::numeric) / total_cnt), 4) as weighted_score,
            ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) as phase1_ratio,
            ROW_NUMBER() OVER(PARTITION BY date ORDER BY avg_trade_value DESC) as trade_value_rank
        FROM theme_aggregation
    )
    , final_ranking AS (
        SELECT 
            to_char(date, 'YYYY-MM-DD') as date_str
            , date
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY weighted_score DESC, phase1_ratio DESC, total_cnt DESC) as global_rank
            , theme_name
            , trade_value_rank
        FROM final_ratio
        WHERE trade_value_rank <= 100
    )
    , target_phase1_stocks AS (
        SELECT 
            f.date,
            f.date_str,
            f.global_rank as theme_rank,
            f.theme_name,
            p.stock_code,
            p.stock_name
        FROM final_ranking f
        JOIN industry.theme_name_list nt ON f.theme_name = nt.theme_name
        JOIN phase_classification p ON nt.stock_code = p.stock_code AND f.date = p.date
        WHERE p.phase = 1
    )
    , future_prices AS (
        -- For a date range backtest, window functions over the filtered price table are easier and fast enough
        SELECT 
            date,
            stock_code,
            close,
            high,
            LEAD(close, 5) OVER(PARTITION BY stock_code ORDER BY date) as close_after_5d,
            MAX(high) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 1 FOLLOWING AND 5 FOLLOWING) as max_high_in_5d
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= '2026-03-30'::date 
    )
    SELECT 
        t.date_str as "기준일"
        , t.theme_rank::varchar as "테마순위"
        , t.theme_name as "테마명"
        , t.stock_name as "종목명"
        , fp.close as "당일_종가(매수단가)"
        , fp.close_after_5d as "5일후_종가"
        , ROUND(((fp.close_after_5d - fp.close) / fp.close) * 100, 2) as "5일후_종가_수익률(%)"
        , fp.max_high_in_5d as "향후5일_최고가"
        , ROUND(((fp.max_high_in_5d - fp.close) / fp.close) * 100, 2) as "향후5일_최고가_수익률(%)"
    FROM target_phase1_stocks t
    JOIN future_prices fp ON t.stock_code = fp.stock_code AND t.date = fp.date
    ORDER BY 
        t.date DESC
        , t.theme_rank ASC
        , "향후5일_최고가_수익률(%)" DESC NULLS LAST
    LIMIT 20;
    """
    df = pd.read_sql_query(query, conn)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df)
finally:
    conn.close()
