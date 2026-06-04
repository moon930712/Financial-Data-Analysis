import os
import psycopg2
import pandas as pd
import numpy as np
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
try:
    print("Connecting to DB...")
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    print("Fetching Top 10 Theme Stocks and their Phases...")
    query_top_stocks = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2026-01-01' AND date <= '2026-05-15'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2025-12-01' AND m.date <= '2026-05-15'
    )
    , phase_calc AS (
        SELECT date, stock_code
            , CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN 1
                WHEN histogram < 0 AND histogram <= lag_histogram THEN 2
                WHEN histogram >= 0 AND histogram > lag_histogram THEN 3
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4
                ELSE 4
            END AS phase
        FROM histo_base
        WHERE date IN (SELECT date FROM valid_dates)
    )
    , theme_aggregation AS (
        SELECT nt.theme_name, p.date
            , COUNT(*) AS total_cnt
            , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) AS phase1_cnt
            , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) AS phase2_cnt
            , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) AS phase3_cnt
            , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) AS phase4_cnt
            , COALESCE(SUM(v1.trade_value), 0) / COUNT(*) AS avg_trade_value
        FROM industry.theme_name_list nt 
        INNER JOIN phase_calc p ON nt.stock_code = p.stock_code
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
        SELECT date, theme_name, global_rank
        FROM (
            SELECT date, theme_name
                , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                    ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                    ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                    total_cnt DESC
                  ) AS global_rank
            FROM trade_rank_calc
            WHERE trade_value_rank <= 150
        ) ranked
        WHERE global_rank <= 10
    )
    SELECT DISTINCT f.date, nt.stock_code, p.phase
    FROM final_ranking f
    INNER JOIN industry.theme_name_list nt ON f.theme_name = nt.theme_name
    INNER JOIN phase_calc p ON nt.stock_code = p.stock_code AND f.date = p.date
    WHERE p.phase IN (1, 2, 3, 4)
    """
    df_stocks = pd.read_sql(query_top_stocks, conn)
    df_stocks['date'] = pd.to_datetime(df_stocks['date'])
    
    print("Fetching Daily Prices...")
    query_prices = "SELECT date, stock_code, close FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2026-01-01'"
    df_prices = pd.read_sql(query_prices, conn)
    df_prices['date'] = pd.to_datetime(df_prices['date'])
    
    # Calculate returns
    print("Calculating Returns...")
    all_dates = sorted(df_prices['date'].unique())
    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    df_prices.set_index(['date', 'stock_code'], inplace=True)
    
    results = []
    
    # Group by date to process stocks together
    for base_date, group in df_stocks.groupby('date'):
        if base_date not in date_to_idx: continue
        base_idx = date_to_idx[base_date]
        target_idx = base_idx + 8
        if target_idx >= len(all_dates): continue
        
        target_date = all_dates[target_idx]
        stocks = group['stock_code'].unique()
        
        try:
            bp = df_prices.loc[(base_date, stocks), 'close']
            tp = df_prices.loc[(target_date, stocks), 'close']
        except KeyError:
            continue
            
        common = bp.index.get_level_values('stock_code').intersection(tp.index.get_level_values('stock_code'))
        if len(common) == 0: continue
        
        bp = bp.loc[(base_date, common)]
        tp = tp.loc[(target_date, common)]
        
        ret = (tp.values - bp.values) / bp.values * 100
        
        for sc, r in zip(common, ret):
            phase = group[group['stock_code'] == sc]['phase'].iloc[0]
            results.append({
                'date': base_date,
                'stock_code': sc,
                'phase': phase,
                'return_rate': r
            })
            
    df_res = pd.DataFrame(results)
    
    # Analyze by Phase
    grouped = df_res.groupby('phase')['return_rate'].agg(['mean', 'median', 'max', 'count', lambda x: (x > 0).mean() * 100])
    grouped.columns = ['Avg Return (%)', 'Median Return (%)', 'Max Return (%)', 'Sample Count', 'Win Rate (%)']
    print("\n================ INDIVIDUAL STOCK RETURN BY PHASE (Inside TOP 10 Themes) ================")
    print(grouped.to_string())
    
    conn.close()

except Exception as e:
    import traceback
    traceback.print_exc()
