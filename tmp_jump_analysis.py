import os
import psycopg2
import pandas as pd
import warnings

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
    print("Connecting to DB...")
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # Massive query to get all theme ranks for 2026 Jan ~ May
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
    
    print("Executing massive rank query...")
    df_ranks = pd.read_sql(query_ranks, conn)
    print(f"Retrieved {len(df_ranks)} rank records.")
    
    # Calculate prev rank
    df_ranks['prev_rank'] = df_ranks.groupby('theme_name')['global_rank'].shift(1)
    
    # Find jump events: prev_rank >= 140, current_rank <= 10
    jump_events = df_ranks[(df_ranks['prev_rank'] >= 140) & (df_ranks['global_rank'] <= 10)]
    
    # Let's also check a slightly looser jump if strict returns 0. e.g. 120 -> 20
    jump_events_loose = df_ranks[(df_ranks['prev_rank'] >= 120) & (df_ranks['global_rank'] <= 20)]
    
    print(f"\nFound {len(jump_events)} extreme jump events (140-150 -> 1-10).")
    print(f"Found {len(jump_events_loose)} loose jump events (120-150 -> 1-20).")
    
    all_jump_data = []
    
    def get_returns_for_event(dt, theme_name, rank, prev_rank):
        # Query 8-day future return for THIS theme starting at THIS dt
        q = f"""
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
        , entry_signals AS (
            SELECT nt.stock_code, '{theme_name}' as theme_name
                , (
                    SELECT close 
                    FROM visual.vsl_anly_stocks_price_subindex01 
                    WHERE stock_code = nt.stock_code AND date = '{dt}'::date 
                    LIMIT 1
                ) AS entry_price
            FROM industry.theme_name_list nt
            WHERE nt.theme_name = '{theme_name}'
        )
        SELECT e.theme_name, '{dt}' as base_date, {rank} as rank, {prev_rank} as prev_rank
            , ROUND(AVG(((v.close - e.entry_price) / NULLIF(e.entry_price, 0)::numeric) * 100), 2) AS return_rate
        FROM entry_signals e
        INNER JOIN visual.vsl_anly_stocks_price_subindex01 v ON e.stock_code = v.stock_code
        WHERE v.date IN (SELECT date FROM target_dates WHERE date > '{dt}'::date)
        GROUP BY e.theme_name
        """
        try:
            return pd.read_sql(q, conn)
        except:
            return pd.DataFrame()

    if not jump_events.empty:
        for idx, row in jump_events.iterrows():
            df_ret = get_returns_for_event(row['date'], row['theme_name'], row['global_rank'], row['prev_rank'])
            all_jump_data.append(df_ret)
            
    elif not jump_events_loose.empty:
        print("\nUsing loose jump events since extreme jumps are 0.")
        for idx, row in jump_events_loose.iterrows():
            df_ret = get_returns_for_event(row['date'], row['theme_name'], row['global_rank'], row['prev_rank'])
            all_jump_data.append(df_ret)
            
    if all_jump_data:
        final_df = pd.concat(all_jump_data, ignore_index=True)
        print("\n--- Jump Events Return Analysis ---")
        print(final_df.to_string(index=False))
        print(f"\nAverage Return for these jump events: {final_df['return_rate'].mean():.2f}%")
    else:
        print("\nNo jump events found to analyze.")
        
    conn.close()
except Exception as e:
    import traceback
    traceback.print_exc()
