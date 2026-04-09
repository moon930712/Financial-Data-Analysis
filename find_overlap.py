import os
import psycopg2
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

def load_env():
    with open(r'c:\Users\Hubnet\antigravity\.env', 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line:
                try:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
                except: pass

load_env()

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', 5432),
    dbname=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

# 2060프로그램매수 종목 추출용 쿼리 (b.date로 모호성 해결)
query_2060 = """
WITH bridge AS(
    SELECT stock_code, reco_date FROM visual.vsl_inv_strat_picks_trend WHERE inv_strat = '2060프로그램매수'
),
histo_base AS(
    SELECT a.stock_code, a.date, b.macd, b.signal, (b.macd-b.signal) AS histogram,
           LAG(b.macd-b.signal) OVER(PARTITION BY a.stock_code ORDER BY a.date) AS lag_histogram,
           LAG(b.macd-b.signal,2) OVER(PARTITION BY a.stock_code ORDER BY a.date) AS lag2_histogram, b.rsi
    FROM visual.vsl_anly_stocks_price_subindex01 a
    JOIN visual.vsl_anly_stocks_price_subindex02 b ON a.stock_code=b.stock_code AND a.date=b.date
),
histo_data AS(
    SELECT stock_code, date, histogram, lag_histogram, lag2_histogram, rsi,
           MIN(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS hist_lowest_14,
           AVG(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_avg_20,
           STDDEV(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_std_20,
           MAX(histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 60 PRECEDING AND 10 PRECEDING) AS max_hist_past
    FROM histo_base
),
base AS(
    SELECT DISTINCT ON(h.date,h.stock_code) h.date, h.stock_code, p.stock_name
    FROM histo_data h
    JOIN visual.vsl_anly_stocks_price_subindex01 p ON h.stock_code=p.stock_code AND h.date=p.date
    WHERE EXISTS(SELECT 1 FROM bridge b WHERE b.stock_code=h.stock_code AND b.reco_date BETWEEN h.date-INTERVAL '5 day' AND h.date)
)
SELECT b.date, b.stock_code, b.stock_name, rsi, 
       (h.lag_histogram-h.hist_avg_20)/NULLIF(h.hist_std_20,0) AS z_score, h.max_hist_past, h.hist_lowest_14
FROM base b
JOIN histo_data h ON b.stock_code=h.stock_code AND b.date=h.date
WHERE b.date >= '2026-03-01'
  AND rsi BETWEEN 30 AND 60
  AND (h.lag_histogram-h.hist_avg_20)/NULLIF(h.hist_std_20,0) <= -2.0
  AND max_hist_past > 0
  AND max_hist_past >= ABS(hist_lowest_14) * 1.2;
"""

# 종가매매2 종목 추출용 쿼리
query_closing = """
WITH base AS(
  SELECT a.date, a.stock_code, a.stock_name
  FROM company.kis_closing_price_sale2 a
  INNER JOIN(
   SELECT stck_bsop_date, stock_code, row_number() OVER(PARTITION BY stock_code,stck_bsop_date ORDER BY stck_cntg_hour DESC) AS rn,
          close, ma_100, lag(close,1) OVER(PARTITION BY stock_code,stck_bsop_date ORDER BY stck_cntg_hour) AS lag_close,
          lag(ma_100,1) OVER(PARTITION BY stock_code,stck_bsop_date ORDER BY stck_cntg_hour) AS lag_ma100
   FROM company.kis_15min_candles
  ) md ON a.stock_code = md.stock_code AND a.date = TO_DATE(md.stck_bsop_date, 'yyyyMMdd')
  WHERE md.rn=1 AND ( (md.lag_close < md.lag_ma100 AND md.ma_100 < md.close) OR md.ma_100 < md.close )
)
SELECT date, stock_code, stock_name FROM base WHERE date >= '2026-03-01';
"""

print("2060프로그램매수 종목 추출 중...")
df_2060 = pd.read_sql_query(query_2060, conn)
print("종가매매 종목 추출 중...")
df_closing = pd.read_sql_query(query_closing, conn)

conn.close()

df_2060['date'] = pd.to_datetime(df_2060['date']).dt.date
df_closing['date'] = pd.to_datetime(df_closing['date']).dt.date

overlap = pd.merge(df_2060, df_closing, on=['date', 'stock_code', 'stock_name'], how='inner')

if overlap.empty:
    print("\n최근 3월 이후 2060프로그램매수와 종가매매가 동시에 포착된 종목이 없습니다.")
else:
    print("\n--- [2060프로그램매수 & 종가매매 중복 포착 종목 리스트] ---")
    print(overlap[['date', 'stock_code', 'stock_name']].sort_values(by='date', ascending=False))
