import os
import psycopg2
import pandas as pd
import numpy as np
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

def get_returns_for_event(dt, theme_name, conn):
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
    SELECT e.theme_name, '{dt}' as base_date
        , ROUND(AVG(((v.close - e.entry_price) / NULLIF(e.entry_price, 0)::numeric) * 100), 2) AS return_rate
    FROM entry_signals e
    INNER JOIN visual.vsl_anly_stocks_price_subindex01 v ON e.stock_code = v.stock_code
    WHERE v.date IN (SELECT date FROM target_dates WHERE date > '{dt}'::date)
    GROUP BY e.theme_name
    """
    try:
        return pd.read_sql(q, conn)['return_rate'].mean()
    except:
        return np.nan

def run_analysis():
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # Query ranks (same logic as before)
    query_ranks = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2025-10-01' AND date <= '2026-05-15'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2025-09-01' AND m.date <= '2026-05-15'
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
    
    print("Fetching ranks...")
    df_ranks = pd.read_sql(query_ranks, conn)
    
    # Sort and calculate lag ranks
    df_ranks = df_ranks.sort_values(['theme_name', 'date']).reset_index(drop=True)
    for i in range(1, 5):
        df_ranks[f'rank_t_{i}'] = df_ranks.groupby('theme_name')['global_rank'].shift(i)
        
    df_ranks.dropna(subset=[f'rank_t_{i}' for i in range(1, 5)], inplace=True)
    
    # Target: Current rank <= 10
    top_entries = df_ranks[df_ranks['global_rank'] <= 10]
    
    results_cond1 = []
    results_cond2 = []
    
    print("Evaluating events...")
    for idx, row in top_entries.iterrows():
        ranks_past = [row[f'rank_t_{i}'] for i in range(4, 0, -1)] # t-4, t-3, t-2, t-1
        
        # Condition 1: 101~145 -> 61~100 -> 1~10
        # Check if there is an index i and j such that i < j, ranks_past[i] is in 101~145, ranks_past[j] is in 61~100
        cond1_met = False
        for i in range(len(ranks_past)):
            if 101 <= ranks_past[i] <= 145:
                for j in range(i+1, len(ranks_past)):
                    if 61 <= ranks_past[j] <= 100:
                        cond1_met = True
                        break
            if cond1_met: break
                
        if cond1_met:
            results_cond1.append(row)
            
        # Condition 2: 146~150 -> 1~10 within 4 days
        cond2_met = any(146 <= r <= 150 for r in ranks_past)
        if cond2_met:
            # Determine path type for analysis
            path_max = max(ranks_past)
            path_min_past = min(ranks_past)
            
            # categorize path
            has_61_100 = any(61 <= r <= 100 for r in ranks_past)
            has_31_60 = any(31 <= r <= 60 for r in ranks_past)
            has_11_30 = any(11 <= r <= 30 for r in ranks_past)
            
            path_desc = "Direct Jump"
            if has_11_30: path_desc = "Via 상위(11-30)"
            elif has_31_60: path_desc = "Via 중위(31-60)"
            elif has_61_100: path_desc = "Via 중하위(61-100)"
            
            row_copy = row.copy()
            row_copy['path_desc'] = path_desc
            row_copy['ranks_path'] = str(ranks_past)
            results_cond2.append(row_copy)
            
    df_cond1 = pd.DataFrame(results_cond1)
    df_cond2 = pd.DataFrame(results_cond2)
    
    print(f"Found {len(df_cond1)} events for Condition 1 (101~145 -> 61~100 -> 1~10)")
    print(f"Found {len(df_cond2)} events for Condition 2 (146~150 -> 1~10 within 4 days)")
    
    # Calculate returns for condition 1
    if not df_cond1.empty:
        rets = []
        for idx, row in df_cond1.iterrows():
            ret = get_returns_for_event(row['date'], row['theme_name'], conn)
            rets.append(ret)
        df_cond1['return'] = rets
        df_cond1 = df_cond1.dropna(subset=['return'])
        
        avg_ret1 = df_cond1['return'].mean()
        med_ret1 = df_cond1['return'].median()
        win_rate1 = (df_cond1['return'] > 0).mean() * 100
        
        print("\n=== 1. 최하위(101~145) -> 중하위(61~100) -> 최상위(1~10) ===")
        print(f"총 발생 건수: {len(df_cond1)}건")
        print(f"평균 수익률: {avg_ret1:.2f}%")
        print(f"중앙값 수익률: {med_ret1:.2f}%")
        print(f"승률(수익률 > 0): {win_rate1:.2f}%")

    # Calculate returns for condition 2
    if not df_cond2.empty:
        rets = []
        for idx, row in df_cond2.iterrows():
            ret = get_returns_for_event(row['date'], row['theme_name'], conn)
            rets.append(ret)
        df_cond2['return'] = rets
        df_cond2 = df_cond2.dropna(subset=['return'])
        
        avg_ret2 = df_cond2['return'].mean()
        med_ret2 = df_cond2['return'].median()
        win_rate2 = (df_cond2['return'] > 0).mean() * 100
        
        print("\n=== 2. 최최하위(146~150)에서 4일 이내 최상위(1~10) 진입 ===")
        print(f"총 발생 건수: {len(df_cond2)}건")
        print(f"평균 수익률: {avg_ret2:.2f}%")
        print(f"중앙값 수익률: {med_ret2:.2f}%")
        print(f"승률(수익률 > 0): {win_rate2:.2f}%")
        
        print("\n=== 3. 최최하위 -> 최상위 진입 과정별 분석 ===")
        grouped = df_cond2.groupby('path_desc').agg(
            건수=('return', 'count'),
            평균수익률=('return', 'mean'),
            중앙값수익률=('return', 'median'),
            승률=('return', lambda x: (x > 0).mean() * 100)
        ).reset_index()
        print(grouped.to_string(index=False))

    conn.close()

if __name__ == "__main__":
    run_analysis()
