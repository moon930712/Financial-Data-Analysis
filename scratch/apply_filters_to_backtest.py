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

def main():
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    print("Loading raw backtest data...")
    df_raw = pd.read_excel('backtest_super_patterns_stocks.xlsx', sheet_name='Raw Data')
    
    df_names = pd.read_sql("SELECT DISTINCT stock_code, stock_name FROM industry.theme_name_list", conn)
    name_to_code = dict(zip(df_names['stock_name'], df_names['stock_code']))
    
    results = []
    
    print(f"Applying filters (Volume Spike >= 1.8 & Smart Money >= 130,000) to {len(df_raw)} stocks...")
    
    for idx, row in df_raw.iterrows():
        dt = row['Signal Date']
        sc = name_to_code.get(row['Stock Name'])
        
        if not sc:
            continue
            
        # 1. Volume Spike (20-day avg)
        q_price = f"""
            SELECT trade_value FROM visual.vsl_anly_stocks_price_subindex01 
            WHERE stock_code = '{sc}' AND date <= '{dt}' ORDER BY date DESC LIMIT 21
        """
        df_p = pd.read_sql(q_price, conn)
        if len(df_p) < 21:
            continue
            
        current_vol = df_p.iloc[0]['trade_value']
        avg_vol = df_p.iloc[1:]['trade_value'].mean()
        if avg_vol == 0:
            continue
            
        vol_spike = current_vol / avg_vol
        if vol_spike < 1.8:
            continue
            
        # 2. Smart Money Flow (Last 3 days)
        q_flow = f"""
            SELECT SUM(CASE WHEN investor IN ('기관합계', '외국인') THEN net_trade_vol ELSE 0 END) as smart_money
            FROM visual.vsl_krx_stocks_investor_shares_trading_info
            WHERE stock_code = '{sc}' AND date <= '{dt}' 
            AND date >= (SELECT MIN(date) FROM (SELECT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date <= '{dt}' GROUP BY date ORDER BY date DESC LIMIT 3) t)
        """
        df_f = pd.read_sql(q_flow, conn)
        smart_money = df_f.iloc[0]['smart_money'] if not df_f.empty and pd.notna(df_f.iloc[0]['smart_money']) else 0
        
        if smart_money < 130000:
            continue
            
        row_dict = row.to_dict()
        row_dict['Volume Spike (Times)'] = round(vol_spike, 2)
        row_dict['Smart Money Flow (3 Days)'] = smart_money
        results.append(row_dict)
        
    df_filtered = pd.DataFrame(results)
    
    if df_filtered.empty:
        print("No stocks passed the strict filters.")
        return
        
    # Calculate Summary
    summary = df_filtered.groupby('Pattern').agg(
        Total_Count=('Stock Name', 'count'),
        Win_Count_D5=('D+5 Return (%)', lambda x: (x > 0).sum()),
        Win_Count_AnyDay=('Max 5-Day Return (%)', lambda x: (x > 0).sum()),
        Avg_D5_Return=('D+5 Return (%)', 'mean')
    ).reset_index()
    
    summary['D+5 종가 승률 (%)'] = round((summary['Win_Count_D5'] / summary['Total_Count']) * 100, 2)
    summary['5일 내 고점 승률 (%)'] = round((summary['Win_Count_AnyDay'] / summary['Total_Count']) * 100, 2)
    summary['평균 D+5 수익률 (%)'] = round(summary['Avg_D5_Return'], 2)
    
    summary = summary[['Pattern', 'Total_Count', 'D+5 종가 승률 (%)', '5일 내 고점 승률 (%)', '평균 D+5 수익률 (%)']]
    summary.columns = ['테마 패턴', '검색된 종목 수', 'D+5 종가 승률 (%)', '5일 내 고점 승률 (%)', '평균 D+5 수익률 (%)']
    
    sort_order = {'6등급 -> 4등급 -> 1등급': 1, '4등급 -> 3등급 -> 1등급': 2, '4등급 -> 2등급 -> 2등급': 3}
    summary['sort_key'] = summary['테마 패턴'].map(sort_order)
    summary = summary.sort_values('sort_key').drop(columns='sort_key')
    
    # Save to Excel
    excel_path = 'backtest_super_patterns_filtered_v2.xlsx'
    with pd.ExcelWriter(excel_path) as writer:
        df_filtered.to_excel(writer, sheet_name='Raw Data', index=False)
        summary.to_excel(writer, sheet_name='Summary', index=False)
        
    print(f"Filtered raw 2503 stocks down to {len(df_filtered)} highly probable stocks.")
    print("\n=== Strict Filter Summary ===")
    print(summary.to_string(index=False))
    print(f"\nSaved to {excel_path} with 2 sheets.")
    
    conn.close()

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    main()
