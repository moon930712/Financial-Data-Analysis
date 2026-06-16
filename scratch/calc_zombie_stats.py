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

query_themes = """
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
SELECT date, theme_name, CASE WHEN global_rank <= 25 THEN '1등급' WHEN global_rank <= 50 THEN '2등급' WHEN global_rank <= 75 THEN '3등급' WHEN global_rank <= 100 THEN '4등급' WHEN global_rank <= 125 THEN '5등급' ELSE '6등급' END AS grade
FROM final_ranking ORDER BY theme_name, date
"""

df_themes = pd.read_sql(query_themes, conn)
df_themes['date'] = pd.to_datetime(df_themes['date'])

df_cycles = pd.read_excel('scratch/analyze_theme_cycle_with_prices_compact.xlsx', sheet_name='Cycles(Summary)')

query_prices = """
SELECT nt.theme_name, v.date, AVG(v.close) as avg_price
FROM industry.theme_name_list nt
JOIN visual.vsl_anly_stocks_price_subindex01 v ON nt.stock_code = v.stock_code
WHERE v.date >= '2023-10-01' AND v.close > 1000
GROUP BY nt.theme_name, v.date
"""
df_prices = pd.read_sql(query_prices, conn)
df_prices['date'] = pd.to_datetime(df_prices['date'])
conn.close()

df = df_themes.merge(df_prices, on=['theme_name', 'date'], how='inner')

results = []
for idx, row in df_cycles.iterrows():
    theme = row['테마명']
    if pd.isna(theme): continue
    last_6_date = pd.to_datetime(str(row['6등급 날짜'])[:10])
    
    theme_df = df[df['theme_name'] == theme]
    theme_df = theme_df[theme_df['date'] <= last_6_date].sort_values('date', ascending=False)
    
    if theme_df.empty: continue
    
    first_6_date = None
    first_6_price = None
    last_6_price = theme_df.iloc[0]['avg_price']
    
    for i, r in theme_df.iterrows():
        if r['grade'] == '6등급':
            first_6_date = r['date']
            first_6_price = r['avg_price']
        else:
            break
            
    if first_6_date and first_6_date < last_6_date:
        duration = (last_6_date - first_6_date).days
        zombie_return = (last_6_price / first_6_price - 1) * 100
        
        period_df = theme_df[(theme_df['date'] >= first_6_date) & (theme_df['date'] <= last_6_date)]
        min_price = period_df['avg_price'].min()
        mdd = (min_price / first_6_price - 1) * 100
        
        results.append({
            '테마명': theme,
            'First_6': first_6_date,
            'Last_6': last_6_date,
            '기간(일)': duration,
            '좀비구간_수익률(%)': zombie_return,
            '좀비구간_최대손실(MDD)': mdd
        })

res_df = pd.DataFrame(results)

print("=== 6등급 좀비 구간(First 6 -> Last 6) 통계 ===")
print(f"총 사이클 수: {len(res_df)}건")
print(f"평균 머문 기간 (일): {res_df['기간(일)'].mean():.1f}일")
print(f"중앙값 머문 기간 (일): {res_df['기간(일)'].median():.1f}일")
print(f"평균 수익률 (%): {res_df['좀비구간_수익률(%)'].mean():.2f}%")
print(f"중앙값 수익률 (%): {res_df['좀비구간_수익률(%)'].median():.2f}%")
print(f"평균 최대 손실폭(MDD %): {res_df['좀비구간_최대손실(MDD)'].mean():.2f}%")
print(f"마이너스 수익률 마감 비율 (%): {(res_df['좀비구간_수익률(%)'] < 0).mean() * 100:.1f}%")
