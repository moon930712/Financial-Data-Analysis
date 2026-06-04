import psycopg2, os
import pandas as pd
def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
load_env()
def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST')
        , port=os.environ.get('DB_PORT', 5432)
        , dbname=os.environ.get('DB_NAME')
        , user=os.environ.get('DB_USER')
        , password=os.environ.get('DB_PASSWORD')
    )
# 전자파 테마의 모든 종목에 대해 신호 여부를 확인하는 쿼리
sql = """
WITH histo_base AS (
    SELECT 
        m.date, m.stock_code, m.stock_name, (m.macd - m.signal) AS histogram,
        LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram,
        LAG(m.macd - m.signal, 2) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag2_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
histo_stats AS (
    SELECT *, 
        AVG(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_avg_20,
        STDDEV(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_std_20
    FROM histo_base
),
signals AS (
    SELECT s.date, s.stock_code, s.stock_name,
        CASE WHEN s.histogram < 0 AND s.lag2_histogram > s.lag_histogram AND s.lag_histogram < s.histogram AND (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) <= -1.0 THEN 1 ELSE 0 END as low_signal,
        CASE WHEN s.lag_histogram < 0 AND s.histogram >= 0 THEN 1 ELSE 0 END as gc_signal,
        CASE WHEN s.histogram > 0 AND s.lag2_histogram < s.lag_histogram AND s.lag_histogram > s.histogram AND (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) >= 1.0 THEN 1 ELSE 0 END as high_signal,
        CASE WHEN s.lag_histogram > 0 AND s.histogram <= 0 THEN 1 ELSE 0 END as dc_signal
    FROM histo_stats s
    WHERE s.date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02)
)
SELECT nt.stock_name, s.low_signal, s.gc_signal, s.high_signal, s.dc_signal,
       (s.low_signal + s.gc_signal + s.high_signal + s.dc_signal) as total_signals
FROM company.naver_theme nt
LEFT JOIN signals s ON nt.stock_code = s.stock_code
WHERE nt.theme_name = '전자파'
ORDER BY total_signals DESC;
"""
try:
    conn = get_connection()
    df = pd.read_sql(sql, conn)
    print(df.to_string(index=False))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
