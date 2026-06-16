import psycopg2
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

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

env = load_env()
conn = psycopg2.connect(
    host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
    dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
)

query = """
WITH all_valid_dates AS (SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2023-10-01')
, theme_histo_base AS (
    SELECT m.date, m.stock_code, (m.macd - m.signal) AS histogram, LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m WHERE m.date IN (SELECT date FROM all_valid_dates)
)
, theme_phase_classification AS (
    SELECT date, stock_code, CASE WHEN histogram < 0 AND histogram > lag_histogram THEN 1 WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 ELSE 4 END as phase
    FROM theme_histo_base
)
, theme_aggregation AS (
    SELECT nt.theme_name, p.date, COUNT(*) as total_cnt, SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt, SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt, SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt, SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
    FROM industry.theme_name_list nt INNER JOIN theme_phase_classification p ON nt.stock_code = p.stock_code LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    WHERE v1.close > 1000 GROUP BY nt.theme_name, p.date HAVING COUNT(*) >= 5
)
, final_ranking AS (
    SELECT date, theme_name, total_cnt, ROW_NUMBER() OVER(PARTITION BY date ORDER BY ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, total_cnt DESC) AS global_rank
    FROM theme_aggregation
)
, theme_grades AS (
    SELECT date, theme_name, CASE WHEN global_rank <= 25 THEN '1등급' WHEN global_rank <= 50 THEN '2등급' WHEN global_rank <= 75 THEN '3등급' WHEN global_rank <= 100 THEN '4등급' WHEN global_rank <= 125 THEN '5등급' ELSE '6등급' END AS grade
    FROM final_ranking
)
, theme_prices AS (
    SELECT nt.theme_name, v.date, AVG(v.close) as avg_price
    FROM industry.theme_name_list nt
    JOIN visual.vsl_anly_stocks_price_subindex01 v ON nt.stock_code = v.stock_code
    WHERE v.date >= '2023-10-01' AND v.close > 1000
    GROUP BY nt.theme_name, v.date
)
SELECT 
    g.theme_name, g.date, g.grade, p.avg_price,
    LAG(g.grade) OVER(PARTITION BY g.theme_name ORDER BY g.date) as prev_grade,
    LAG(p.avg_price) OVER(PARTITION BY g.theme_name ORDER BY g.date) as prev_price
FROM theme_grades g
JOIN theme_prices p ON g.theme_name = p.theme_name AND g.date = p.date
"""

df = pd.read_sql(query, conn)
conn.close()

df_66 = df[(df['prev_grade'] == '6등급') & (df['grade'] == '6등급')]

if not df_66.empty:
    df_66['daily_return'] = (df_66['avg_price'] / df_66['prev_price'] - 1) * 100
    
    print("=== 6등급 -> 6등급 일일 수익률 통계 ===")
    print(f"총 샘플 일수: {len(df_66)}일")
    print(f"평균 일일 수익률: {df_66['daily_return'].mean():.3f}%")
    print(f"중앙값 일일 수익률: {df_66['daily_return'].median():.3f}%")
    print(f"음수(하락) 발생 확률: {(df_66['daily_return'] < 0).mean() * 100:.1f}%")
else:
    print("No data found")
