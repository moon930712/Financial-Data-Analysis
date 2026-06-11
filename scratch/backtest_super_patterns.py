import os
import psycopg2
import pandas as pd
import numpy as np
import sys

sys.stdout.reconfigure(encoding='utf-8')

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
    if pd.isna(rank): return None
    if rank <= 25: return '1등급'
    elif rank <= 50: return '2등급'
    elif rank <= 75: return '3등급'
    elif rank <= 100: return '4등급'
    elif rank <= 125: return '5등급'
    else: return '6등급'

def run_backtest():
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    query_ranks = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2025-12-01'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2025-11-01'
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
    
    print("Fetching theme ranks...")
    df_ranks = pd.read_sql(query_ranks, conn)
    df_ranks['date'] = pd.to_datetime(df_ranks['date'])
    df_ranks = df_ranks.sort_values(['theme_name', 'date']).reset_index(drop=True)
    
    df_ranks['rank_t_1'] = df_ranks.groupby('theme_name')['global_rank'].shift(1)
    df_ranks['rank_t_2'] = df_ranks.groupby('theme_name')['global_rank'].shift(2)
    df_ranks.dropna(subset=['rank_t_1', 'rank_t_2'], inplace=True)
    
    df_ranks['grade_t_0'] = df_ranks['global_rank'].apply(get_rank_label)
    df_ranks['grade_t_1'] = df_ranks['rank_t_1'].apply(get_rank_label)
    df_ranks['grade_t_2'] = df_ranks['rank_t_2'].apply(get_rank_label)
    
    df_ranks['pattern'] = df_ranks['grade_t_2'] + " -> " + df_ranks['grade_t_1'] + " -> " + df_ranks['grade_t_0']
    
    target_patterns = [
        '6등급 -> 4등급 -> 1등급',
        '4등급 -> 3등급 -> 1등급',
        '4등급 -> 2등급 -> 2등급',
        '3등급 -> 2등급 -> 1등급',
        '3등급 -> 3등급 -> 1등급'
    ]
    
    df_matched = df_ranks[df_ranks['pattern'].isin(target_patterns)].copy()
    df_matched = df_matched[df_matched['date'] >= '2026-01-01']
    
    print(f"Found {len(df_matched)} matched theme events since 2026-01-01.")
    if df_matched.empty:
        print("No events found.")
        return
        
    print("Fetching stock phases...")
    query_stock_phase = """
    WITH histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2025-11-01'
    )
    SELECT date, stock_code, stock_name
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1 -- 회복기
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 2 -- 상승기
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 3 -- 하락기
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 -- 둔화기
            ELSE 4
        END AS phase
    FROM histo_base
    WHERE date >= '2026-01-01'
    """
    df_phases = pd.read_sql(query_stock_phase, conn)
    df_phases['date'] = pd.to_datetime(df_phases['date'])
    
    df_themes = pd.read_sql("SELECT theme_name, stock_code FROM industry.theme_name_list", conn)
    
    df_signals = pd.merge(df_matched, df_themes, on='theme_name', how='inner')
    df_signals = pd.merge(df_signals, df_phases, on=['date', 'stock_code'], how='inner')
    df_signals = df_signals[df_signals['phase'].isin([1, 2])]
    print(f"Total matched stocks (Phase 1 or 2): {len(df_signals)}")
    
    print("Loading prices for return calculations...")
    q_prices = "SELECT date, stock_code, close FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2026-01-01'"
    df_prices = pd.read_sql(q_prices, conn)
    df_prices['date'] = pd.to_datetime(df_prices['date'])
    
    pt_close = df_prices.pivot(index='date', columns='stock_code', values='close')
    date_list = pt_close.index.tolist()
    
    results = []
    for idx, row in df_signals.iterrows():
        dt = row['date']
        sc = row['stock_code']
        
        try:
            date_idx = date_list.index(dt)
        except ValueError:
            continue
            
        future_dates = date_list[date_idx+1 : date_idx+6]
        
        entry_price = pt_close.loc[dt, sc] if sc in pt_close.columns else np.nan
        if pd.isna(entry_price) or entry_price <= 0:
            continue
            
        ret_data = {
            'Signal Date': dt.strftime('%Y-%m-%d'),
            'Theme': row['theme_name'],
            'Pattern': row['pattern'],
            'Stock Name': row['stock_name'],
            'Phase': '회복기(1)' if row['phase'] == 1 else '상승기(2)'
        }
        
        for i, f_dt in enumerate(future_dates):
            f_price = pt_close.loc[f_dt, sc] if sc in pt_close.columns else np.nan
            if not pd.isna(f_price):
                ret_data[f'D+{i+1} Return (%)'] = round(((f_price - entry_price) / entry_price) * 100, 2)
            else:
                ret_data[f'D+{i+1} Return (%)'] = np.nan
                
        results.append(ret_data)
        
    df_final = pd.DataFrame(results)
    df_final = df_final.sort_values(['Signal Date', 'Pattern', 'Theme', 'Stock Name'])
    
    ret_cols = [c for c in df_final.columns if 'Return' in c]
    df_final['Max 5-Day Return (%)'] = df_final[ret_cols].max(axis=1)
    
    excel_path = 'backtest_super_patterns_stocks.xlsx'
    df_final.to_excel(excel_path, index=False)
    
    # Calculate Summary Stats
    summary = df_final.groupby('Pattern').agg(
        Total_Count=('Stock Name', 'count'),
        Win_Count_D5=('D+5 Return (%)', lambda x: (x > 0).sum()),
        Win_Count_AnyDay=('Max 5-Day Return (%)', lambda x: (x > 0).sum()),
        Avg_D5_Return=('D+5 Return (%)', 'mean')
    ).reset_index()
    
    summary['D+5 Win Rate (%)'] = round((summary['Win_Count_D5'] / summary['Total_Count']) * 100, 2)
    summary['Any Day Win Rate (%)'] = round((summary['Win_Count_AnyDay'] / summary['Total_Count']) * 100, 2)
    summary['Avg_D5_Return'] = round(summary['Avg_D5_Return'], 2)
    
    print("\n=== Backtest Summary ===")
    print(summary[['Pattern', 'Total_Count', 'D+5 Win Rate (%)', 'Any Day Win Rate (%)', 'Avg_D5_Return']].to_string(index=False))
    
    print(f"\nSaved full stock-level backtest to {excel_path}")
    conn.close()

if __name__ == "__main__":
    run_backtest()
