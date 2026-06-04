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
    
    print("Fetching Daily Ranks for Themes...")
    query_ranks = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2026-01-01' AND date <= '2026-05-15'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2025-12-01' AND m.date <= '2026-05-15'
    )
    , phase_calc AS (
        SELECT date, stock_code, stock_name
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
        SELECT date, theme_name
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                total_cnt DESC
              ) AS global_rank
        FROM trade_rank_calc
        WHERE trade_value_rank <= 150
    )
    SELECT date, theme_name, global_rank
    FROM final_ranking
    ORDER BY theme_name ASC, date ASC
    """
    df_ranks = pd.read_sql(query_ranks, conn)
    df_ranks['date'] = pd.to_datetime(df_ranks['date'])
    print(f"Retrieved {len(df_ranks)} rank records.")
    
    print("Fetching Daily Prices...")
    query_prices = """
    SELECT date, stock_code, close 
    FROM visual.vsl_anly_stocks_price_subindex01 
    WHERE date >= '2026-01-01'
    """
    df_prices = pd.read_sql(query_prices, conn)
    df_prices['date'] = pd.to_datetime(df_prices['date'])
    print(f"Retrieved {len(df_prices)} price records.")
    
    print("Fetching Theme Mapping...")
    query_themes = "SELECT theme_name, stock_code FROM industry.theme_name_list"
    df_themes = pd.read_sql(query_themes, conn)
    
    conn.close()
    
    print("Computing 8-day future returns for all events...")
    # Get sorted trading dates
    all_dates = sorted(df_prices['date'].unique())
    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    
    # Pre-calculate an easy lookup for theme -> stock_codes
    theme_to_stocks = df_themes.groupby('theme_name')['stock_code'].apply(list).to_dict()
    
    # Pre-index prices for fast lookup
    df_prices.set_index(['date', 'stock_code'], inplace=True)
    
    results = []
    
    for idx, row in df_ranks.iterrows():
        base_date = row['date']
        theme = row['theme_name']
        rank = row['global_rank']
        
        if base_date not in date_to_idx:
            continue
            
        base_idx = date_to_idx[base_date]
        target_idx = base_idx + 8
        
        if target_idx >= len(all_dates):
            continue # not enough future data
            
        target_date = all_dates[target_idx]
        stocks = theme_to_stocks.get(theme, [])
        
        if not stocks:
            continue
            
        # Get prices on base_date
        try:
            base_prices = df_prices.loc[(base_date, stocks), 'close']
        except KeyError:
            continue
            
        # Get prices on target_date
        try:
            target_prices = df_prices.loc[(target_date, stocks), 'close']
        except KeyError:
            continue
            
        # Match stocks that exist in both
        common_stocks = base_prices.index.get_level_values('stock_code').intersection(target_prices.index.get_level_values('stock_code'))
        if len(common_stocks) == 0:
            continue
            
        bp = base_prices.loc[(base_date, common_stocks)].values
        tp = target_prices.loc[(target_date, common_stocks)].values
        
        # Calculate return
        returns = (tp - bp) / bp * 100
        avg_ret = np.mean(returns)
        med_ret = np.median(returns)
        
        results.append({
            'date': base_date,
            'theme_name': theme,
            'global_rank': rank,
            'avg_return': avg_ret,
            'median_return': med_ret
        })

    df_res = pd.DataFrame(results)
    
    # Calculate prev_rank
    df_res = df_res.sort_values(by=['theme_name', 'date'])
    df_res['prev_rank'] = df_res.groupby('theme_name')['global_rank'].shift(1)
    df_res = df_res.dropna(subset=['prev_rank', 'avg_return'])
    
    print(f"Calculated returns for {len(df_res)} valid events.")
    
    # Define bins
    bins = [0, 10, 30, 60, 100, 150]
    labels = ['1.최상위(1~10)', '2.상위(11~30)', '3.중위(31~60)', '4.중하위(61~100)', '5.최하위(101~150)']
    
    df_res['curr_rank_group'] = pd.cut(df_res['global_rank'], bins=bins, labels=labels)
    df_res['prev_rank_group'] = pd.cut(df_res['prev_rank'], bins=bins, labels=labels)
    
    # Group by previous and current rank group
    grouped_mean = df_res.groupby(['prev_rank_group', 'curr_rank_group'], observed=False)['avg_return'].mean().unstack()
    grouped_median = df_res.groupby(['prev_rank_group', 'curr_rank_group'], observed=False)['median_return'].median().unstack()
    grouped_count = df_res.groupby(['prev_rank_group', 'curr_rank_group'], observed=False)['avg_return'].count().unstack()
    
    # We only show cells with at least 5 events to avoid noise
    grouped_mean = grouped_mean.where(grouped_count >= 5, np.nan)
    grouped_median = grouped_median.where(grouped_count >= 5, np.nan)
    
    print("\n================ HEATMAP: AVERAGE 8-DAY RETURN (%) ================")
    print("Rows: PREVIOUS DAY RANK GROUP | Columns: CURRENT DAY RANK GROUP\n")
    
    # Print formatted matrix
    pd.set_option('display.float_format', lambda x: f'{x:6.2f}%' if pd.notnull(x) else '   N/A  ')
    print(grouped_mean)
    
    print("\n================ HEATMAP: MEDIAN 8-DAY RETURN (%) ================")
    print("Rows: PREVIOUS DAY RANK GROUP | Columns: CURRENT DAY RANK GROUP\n")
    print(grouped_median)
    
    print("\n================ EVENT COUNTS (Sample Size) ================")
    pd.set_option('display.float_format', lambda x: f'{x:6.0f}')
    print(grouped_count)

except Exception as e:
    import traceback
    traceback.print_exc()
