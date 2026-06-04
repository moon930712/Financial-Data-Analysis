import os
import psycopg2
import pandas as pd
import numpy as np
import warnings

# Suppress pandas warning about SQLAlchemy
warnings.filterwarnings('ignore', category=UserWarning)

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
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    start_date = pd.to_datetime('2026-01-02')
    end_date = pd.to_datetime('2026-05-15')
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    entry_dates = [d.strftime('%Y-%m-%d') for d in dates]
    
    all_data = []
    
    # Get valid dates from DB so we don't query holidays
    valid_dates_query = "SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2026-01-02' AND date <= '2026-05-15'"
    valid_db_dates_df = pd.read_sql(valid_dates_query, conn)
    valid_db_dates = [d.strftime('%Y-%m-%d') for d in valid_db_dates_df['date'].tolist()]
    
    entry_dates = [d for d in entry_dates if d in valid_db_dates]
    print(f"Total valid trading days to process: {len(entry_dates)}")
    
    for dt in entry_dates:
        query = f"""
        WITH target_dates AS (
            SELECT date FROM (
                SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01
                WHERE date <= '{dt}'::date ORDER BY date DESC LIMIT 1
            ) a
            UNION
            SELECT date FROM (
                SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01
                WHERE date > '{dt}'::date ORDER BY date ASC LIMIT 8
            ) b
        )
        , date_bounds AS (
            SELECT MIN(date) as min_d, MAX(date) as max_d FROM target_dates
        )
        , histo_base AS (
            SELECT m.date, m.stock_code, m.stock_name
                , (m.macd - m.signal) AS histogram
                , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
            FROM visual.vsl_anly_stocks_price_subindex02 m
            WHERE m.date >= (SELECT min_d FROM date_bounds) - INTERVAL '15 days'
                AND m.date <= (SELECT max_d FROM date_bounds)
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
            WHERE date IN (SELECT date FROM target_dates)
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
        , entry_signals AS (
            SELECT p.stock_code, p.stock_name, nt.theme_name
                , (
                    SELECT close 
                    FROM visual.vsl_anly_stocks_price_subindex01 
                    WHERE stock_code = p.stock_code AND date = p.date 
                    LIMIT 1
                ) AS entry_price
            FROM industry.theme_name_list nt 
            INNER JOIN phase_calc p ON nt.stock_code = p.stock_code
            WHERE p.date = '{dt}'::date
                AND p.phase IN (1, 2, 3, 4) 
        )
        , final_result AS (
            SELECT '{dt}' as base_date, v.date, s.theme_name, fr.global_rank
                , ROUND(((v.close - s.entry_price) / NULLIF(s.entry_price, 0)::numeric) * 100, 2) AS return_rate
            FROM entry_signals s
            INNER JOIN visual.vsl_anly_stocks_price_subindex01 v ON s.stock_code = v.stock_code
            LEFT JOIN final_ranking fr ON s.theme_name = fr.theme_name AND v.date = fr.date
            WHERE v.date > '{dt}'::date AND v.date IN (SELECT date FROM target_dates)
        )
        SELECT base_date, theme_name, global_rank, AVG(return_rate) as avg_return
        FROM final_result
        WHERE global_rank IS NOT NULL
        GROUP BY base_date, theme_name, global_rank
        """
        try:
            df = pd.read_sql(query, conn)
            if not df.empty:
                all_data.append(df)
            print(f"Processed {dt}, got {len(df)} records")
        except Exception as e:
            print(f"Error on {dt}: {e}")

    # Filter empty dfs
    valid_dfs = [df for df in all_data if not df.empty]
    if not valid_dfs:
        print("No data retrieved.")
        conn.close()
        exit(1)
        
    final_df = pd.concat(valid_dfs, ignore_index=True)
    final_df.dropna(subset=['global_rank', 'avg_return'], inplace=True)
    
    # Calculate correlation between rank and return
    correlation = final_df['global_rank'].corr(final_df['avg_return'])
    
    # Calculate average return by rank deciles
    bins = [0, 5, 20, 40, 60, 80, 100, 120, 145, 150]
    labels = ['1.(1~5위)', '2.(6~20위)', '3.(21~40위)', '4.(41~60위)', '5.(61~80위)', '6.(81~100위)', '7.(101~120위)', '8.(121~145위)', '9.(146~150위)']
    final_df['rank_group'] = pd.cut(final_df['global_rank'], bins=bins, labels=labels)
    grouped = final_df.groupby('rank_group', observed=False)['avg_return'].mean().reset_index()
    
    print("\n--- Correlation Analysis ---")
    print(f"Total Entry Dates Analyzed: {len(valid_dfs)}")
    print(f"Pearson Correlation (Rank vs Avg Return): {correlation:.4f}")
    print("\n--- Average Return by Rank Group ---")
    print(grouped.to_string(index=False))
    
    conn.close()
except Exception as e:
    import traceback
    traceback.print_exc()
