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

def get_daily_returns_for_event(dt, theme_name, conn):
    # Get the entry date and the next 5 trading dates
    q_dates = f"""
    SELECT date FROM visual.vsl_anly_stocks_price_subindex01
    WHERE date > '{dt}'::date 
    GROUP BY date
    ORDER BY date ASC 
    LIMIT 5
    """
    future_dates_df = pd.read_sql(q_dates, conn)
    future_dates = future_dates_df['date'].astype(str).tolist()
    
    if not future_dates:
        return {f'D+{i}': np.nan for i in range(1, 6)}
        
    dates_str = "'" + "','".join(future_dates) + "'"
    
    q_returns = f"""
    WITH entry_signals AS (
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
    SELECT v.date
        , ROUND(AVG(((v.close - e.entry_price) / NULLIF(e.entry_price, 0)::numeric) * 100), 2) AS avg_return
    FROM entry_signals e
    INNER JOIN visual.vsl_anly_stocks_price_subindex01 v ON e.stock_code = v.stock_code
    WHERE v.date IN ({dates_str})
    GROUP BY v.date
    ORDER BY v.date ASC
    """
    try:
        returns_df = pd.read_sql(q_returns, conn)
        returns_df['date'] = returns_df['date'].astype(str)
        
        # Map the actual dates to D+1, D+2, ..., D+5
        res = {}
        for i, f_date in enumerate(future_dates):
            row = returns_df[returns_df['date'] == f_date]
            if not row.empty:
                res[f'D+{i+1}'] = row['avg_return'].values[0]
            else:
                res[f'D+{i+1}'] = np.nan
                
        # Fill missing up to D+5
        for i in range(1, 6):
            if f'D+{i}' not in res:
                res[f'D+{i}'] = np.nan
        return res
    except:
        return {f'D+{i}': np.nan for i in range(1, 6)}

def run_analysis():
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
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
    df_ranks = df_ranks.sort_values(['theme_name', 'date']).reset_index(drop=True)
    for i in range(1, 5):
        df_ranks[f'rank_t_{i}'] = df_ranks.groupby('theme_name')['global_rank'].shift(i)
        
    df_ranks.dropna(subset=[f'rank_t_{i}' for i in range(1, 5)], inplace=True)
    top_entries = df_ranks[df_ranks['global_rank'] <= 10]
    
    results = []
    
    print("Evaluating events and fetching daily returns...")
    for idx, row in top_entries.iterrows():
        ranks_past = [row[f'rank_t_{i}'] for i in range(4, 0, -1)]
        
        # Condition 1
        cond1_met = False
        for i in range(len(ranks_past)):
            if 101 <= ranks_past[i] <= 145:
                for j in range(i+1, len(ranks_past)):
                    if 61 <= ranks_past[j] <= 100:
                        cond1_met = True
                        break
            if cond1_met: break
            
        # Condition 2
        cond2_met = any(146 <= r <= 150 for r in ranks_past)
        
        if cond1_met or cond2_met:
            daily_returns = get_daily_returns_for_event(row['date'], row['theme_name'], conn)
            
            base_info = {
                'Date': row['date'].strftime('%Y-%m-%d'),
                'Theme Name': row['theme_name'],
                'Rank(D-day)': row['global_rank'],
                'Ranks(Past 4 Days)': str(ranks_past)
            }
            
            if cond1_met:
                item1 = base_info.copy()
                item1['Condition'] = '1. 최하위(101~145) -> 중하위(61~100) -> 최상위(1~10)'
                item1['Path Description'] = '점진적 상승'
                item1.update(daily_returns)
                results.append(item1)
                
            if cond2_met:
                item2 = base_info.copy()
                item2['Condition'] = '2. 최최하위(146~150) -> 최상위(1~10) 4일이내 진입'
                
                path_desc = "Direct Jump"
                if any(11 <= r <= 30 for r in ranks_past): path_desc = "Via 상위(11-30)"
                elif any(31 <= r <= 60 for r in ranks_past): path_desc = "Via 중위(31-60)"
                elif any(61 <= r <= 100 for r in ranks_past): path_desc = "Via 중하위(61-100)"
                item2['Path Description'] = path_desc
                item2.update(daily_returns)
                results.append(item2)

    df_final = pd.DataFrame(results)
    
    # Calculate Summary for Condition 1 & 2
    summary_data = []
    
    if not df_final.empty:
        # Reorder columns
        cols = ['Condition', 'Path Description', 'Date', 'Theme Name', 'Rank(D-day)', 'Ranks(Past 4 Days)', 'D+1', 'D+2', 'D+3', 'D+4', 'D+5']
        df_final = df_final[cols]
        
        for cond in df_final['Condition'].unique():
            df_cond = df_final[df_final['Condition'] == cond]
            for path in df_cond['Path Description'].unique():
                df_path = df_cond[df_cond['Path Description'] == path]
                
                summary_data.append({
                    'Condition': cond,
                    'Path Description': path,
                    'Count': len(df_path),
                    'D+1 (Avg/Med)': f"{df_path['D+1'].mean():.2f}% / {df_path['D+1'].median():.2f}%",
                    'D+2 (Avg/Med)': f"{df_path['D+2'].mean():.2f}% / {df_path['D+2'].median():.2f}%",
                    'D+3 (Avg/Med)': f"{df_path['D+3'].mean():.2f}% / {df_path['D+3'].median():.2f}%",
                    'D+4 (Avg/Med)': f"{df_path['D+4'].mean():.2f}% / {df_path['D+4'].median():.2f}%",
                    'D+5 (Avg/Med)': f"{df_path['D+5'].mean():.2f}% / {df_path['D+5'].median():.2f}%"
                })
                
    df_summary = pd.DataFrame(summary_data)
    
    excel_path = 'jump_analysis_daily_returns.xlsx'
    with pd.ExcelWriter(excel_path) as writer:
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        df_final.to_excel(writer, sheet_name='Raw Data', index=False)
        
    print(f"Analysis saved to {excel_path}")
    conn.close()

if __name__ == "__main__":
    run_analysis()
