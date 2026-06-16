import pandas as pd
import psycopg2
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

df_prices = pd.read_excel('scratch/analyze_theme_cycle_with_prices_compact.xlsx', sheet_name='Prices_Pivot_Compact')
df_61 = df_prices[df_prices['6 -N패턴'] == '6 - 1패턴'].copy()

# Calculate return on D+1
df_61['d1_return'] = (df_61['D+1'] / df_61['D+0'] - 1) * 100
theme_returns = df_61.groupby(['테마명', '시작일(Point A)']).agg({'d1_return': 'mean'}).reset_index()

# Profitable: average D+1 return > 0%
theme_returns['is_profitable'] = theme_returns['d1_return'] > 0
results = []

for idx, row in theme_returns.iterrows():
    theme = row['테마명']
    if pd.isna(theme): continue
    d0_date = pd.to_datetime(str(row['시작일(Point A)'])[:10])
    
    query_d1 = f"SELECT MIN(date) as d1_date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date > '{d0_date.strftime('%Y-%m-%d')}'"
    df_d1 = pd.read_sql(query_d1, conn)
    if df_d1.empty or pd.isna(df_d1.iloc[0]['d1_date']): continue
    d1_date = df_d1.iloc[0]['d1_date']
    
    query = f"""
    WITH smart_money AS (
        SELECT date, stock_code, SUM(CASE WHEN investor IN ('기관합계', '외국인') THEN net_trade_vol ELSE 0 END) as sm_flow
        FROM visual.vsl_krx_stocks_investor_shares_trading_info
        WHERE date = '{d1_date.strftime('%Y-%m-%d')}'
        GROUP BY date, stock_code
    )
    SELECT COUNT(v1.stock_code) as stock_cnt, SUM(v1.trade_value) as total_trade_value, AVG(v1.trade_value) as avg_trade_value, SUM(COALESCE(sm.sm_flow, 0)) as total_sm_flow
    FROM visual.vsl_anly_stocks_price_subindex01 v1
    JOIN industry.theme_name_list nt ON v1.stock_code = nt.stock_code
    LEFT JOIN smart_money sm ON v1.stock_code = sm.stock_code AND v1.date = sm.date
    WHERE nt.theme_name = '{theme}' AND v1.date = '{d1_date.strftime('%Y-%m-%d')}'
    """
    df_db = pd.read_sql(query, conn)
    if not df_db.empty and df_db.iloc[0]['stock_cnt'] > 0:
        results.append({
            '테마명': theme,
            'is_profitable': row['is_profitable'],
            '수익률': row['d1_return'],
            '종목수': df_db.iloc[0]['stock_cnt'],
            '총거래대금': df_db.iloc[0]['total_trade_value'],
            '평균거래대금': df_db.iloc[0]['avg_trade_value'],
            '스마트머니': df_db.iloc[0]['total_sm_flow']
        })

conn.close()

df_res = pd.DataFrame(results)
if df_res.empty:
    print("No valid records found.")
else:
    prof = df_res[df_res['is_profitable'] == True]
    unprof = df_res[df_res['is_profitable'] == False]

    print("=== 6->1 진짜 1등급(수익) vs 가짜 1등급(소외) 비교 ===")
    print(f"진짜 1등급(수익 발생) 건수: {len(prof)}건")
    print(f"가짜 1등급(수익 미발생) 건수: {len(unprof)}건\n")

    print("[1. 테마 규모 (평균 종목 수)]")
    print(f"  - 진짜 1등급: {prof['종목수'].mean():.1f}개")
    print(f"  - 가짜 1등급: {unprof['종목수'].mean():.1f}개")

    print("\n[2. 돌파 당일(D+1) 평균 총 거래대금]")
    print(f"  - 진짜 1등급: {prof['총거래대금'].mean():,.0f}원")
    print(f"  - 가짜 1등급: {unprof['총거래대금'].mean():,.0f}원")

    print("\n[3. 돌파 당일(D+1) 평균 스마트머니(외인/기관 순매수)]")
    print(f"  - 진짜 1등급: {prof['스마트머니'].mean():,.0f}주")
    print(f"  - 가짜 1등급: {unprof['스마트머니'].mean():,.0f}주")
