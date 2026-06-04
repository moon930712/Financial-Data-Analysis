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

def get_rank_label(rank):
    if pd.isna(rank):
        return None
    if rank <= 20:
        return '최상위'
    elif rank <= 40:
        return '상위'
    elif rank <= 60:
        return '중상위'
    elif rank <= 90:
        return '중위'
    elif rank <= 110:
        return '중하위'
    elif rank <= 130:
        return '하위'
    else:
        return '최하위'

def run_analysis():
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # Get Ranks (Same as before)
    query_ranks = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2025-01-02' AND date <= '2026-05-15'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2024-12-01' AND m.date <= '2026-05-15'
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
    df_ranks['date'] = pd.to_datetime(df_ranks['date'])
    df_ranks = df_ranks.sort_values(['theme_name', 'date']).reset_index(drop=True)
    
    for i in range(1, 5):
        df_ranks[f'rank_t_{i}'] = df_ranks.groupby('theme_name')['global_rank'].shift(i)
        
    df_ranks.dropna(subset=[f'rank_t_{i}' for i in range(1, 5)], inplace=True)
    
    valid_dates_query = "SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2025-01-02' ORDER BY date"
    df_dates = pd.read_sql(valid_dates_query, conn)
    date_list = df_dates['date'].astype(str).tolist()
    
    next_5_days = {}
    for i, d in enumerate(date_list):
        next_5_days[d] = date_list[i+1:i+6]
        
    print("Fetching daily theme returns for unfiltered analysis...")
    q_all_prices = """
    SELECT v.date, v.stock_code, v.close, nt.theme_name
    FROM visual.vsl_anly_stocks_price_subindex01 v
    INNER JOIN industry.theme_name_list nt ON v.stock_code = nt.stock_code
    WHERE v.date >= '2025-01-02'
    """
    df_prices = pd.read_sql(q_all_prices, conn)
    df_prices['date'] = df_prices['date'].astype(str)
    
    print("Processing events (Unfiltered Robustness Check)...")
    results = []
    
    df_prices_unique = df_prices[['date', 'stock_code', 'close']].drop_duplicates()
    pt_close = df_prices_unique.pivot(index='date', columns='stock_code', values='close')
    
    theme_stocks = df_prices.groupby('theme_name')['stock_code'].unique().to_dict()
    
    count_total = 0
    
    for idx, row in df_ranks.iterrows():
        dt = row['date'].strftime('%Y-%m-%d')
        theme = row['theme_name']
        
        future_dts = next_5_days.get(dt, [])
        if not future_dts:
            continue
            
        stocks = theme_stocks.get(theme, [])
        if len(stocks) == 0:
            continue
            
        try:
            entry_prices = pt_close.loc[dt, stocks]
            valid_stocks = entry_prices.dropna().index
            if len(valid_stocks) == 0:
                continue
                
            entry_prices = entry_prices[valid_stocks]
            
            daily_returns = []
            
            for f_dt in future_dts:
                if f_dt not in pt_close.index:
                    daily_returns.append(None)
                    continue
                future_prices = pt_close.loc[f_dt, valid_stocks]
                
                valid_mask = future_prices.notna() & (entry_prices > 0)
                if not valid_mask.any():
                    daily_returns.append(None)
                    continue
                
                ret = ((future_prices[valid_mask] - entry_prices[valid_mask]) / entry_prices[valid_mask]).mean() * 100
                daily_returns.append(ret)
                
            while len(daily_returns) < 5:
                daily_returns.append(None)
                
            valid_returns_only = [r for r in daily_returns if r is not None]
            if not valid_returns_only: continue
            
            count_total += 1
            
            max_return = max(valid_returns_only)
            min_return = min(valid_returns_only)
            unfiltered_return = valid_returns_only[-1] # 보유했을 때의 최종 수익률 (통상 D+5)
            
            # 승패 로직 (선착순 도달)
            hit_status = "None"
            for r in valid_returns_only:
                if r >= 3.0:
                    hit_status = "Win (+3%)"
                    break
                elif r <= -3.0:
                    hit_status = "Loss (-3%)"
                    break
                    
            # Build pattern string (3 days: D-2, D-1, D-day)
            ranks = [row[f'rank_t_{i}'] for i in range(2, 0, -1)] + [row['global_rank']]
            labels = [get_rank_label(r) for r in ranks]
            pattern_str = " -> ".join(labels)
            
            results.append({
                'Date': dt,
                'Theme Name': theme,
                'Pattern': pattern_str,
                'Hit Status': hit_status,
                'Unfiltered D+5 Return (%)': round(unfiltered_return, 2),
                'Max 5-Day Return (%)': round(max_return, 2),
                'Min 5-Day Return (%)': round(min_return, 2)
            })
        except KeyError:
            continue
            
    print(f"Total events analyzed (All occurrences without filter): {count_total}")
    
    if results:
        df_res = pd.DataFrame(results)
        
        # Calculate aggregations per pattern
        pattern_summary = []
        for pattern, group in df_res.groupby('Pattern'):
            total = len(group)
            wins = len(group[group['Hit Status'] == 'Win (+3%)'])
            losses = len(group[group['Hit Status'] == 'Loss (-3%)'])
            nones = len(group[group['Hit Status'] == 'None'])
            
            win_rate = (wins / total) * 100
            loss_rate = (losses / total) * 100
            
            mean_unfiltered = group['Unfiltered D+5 Return (%)'].mean()
            mean_max = group['Max 5-Day Return (%)'].mean()
            mean_min = group['Min 5-Day Return (%)'].mean()
            
            pattern_summary.append({
                'Pattern': pattern,
                'Total Count': total,
                'Win (+3%) Count': wins,
                'Loss (-3%) Count': losses,
                'Win Rate (%)': round(win_rate, 2),
                'Loss Rate (%)': round(loss_rate, 2),
                'Avg D+5 Return (%)': round(mean_unfiltered, 2),
                'Avg Max Return (%)': round(mean_max, 2),
                'Avg Min Return (%)': round(mean_min, 2)
            })
            
        df_summary = pd.DataFrame(pattern_summary)
        # Sort by Unfiltered Expected Return (D+5)
        df_summary = df_summary.sort_values('Avg D+5 Return (%)', ascending=False)
        
        print("\n=== Robustness Check Results (Top 15 by Unfiltered Avg Return, Min Count 50) ===")
        filtered_summary = df_summary[df_summary['Total Count'] >= 50].head(15)
        print(filtered_summary.to_string(index=False))
        
        excel_path = 'pattern_robustness_analysis.xlsx'
        with pd.ExcelWriter(excel_path) as writer:
            df_summary.to_excel(writer, sheet_name='Robustness Summary', index=False)
            df_res.to_excel(writer, sheet_name='Raw Data', index=False)
            
        print(f"\nAnalysis saved to {excel_path}")
    else:
        print("No events met the criteria.")
        
    conn.close()

if __name__ == "__main__":
    run_analysis()
