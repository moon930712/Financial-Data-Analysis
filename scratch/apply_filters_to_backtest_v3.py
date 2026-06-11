# -*- coding: utf-8 -*-
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

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    env = load_env()
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    print("Loading raw backtest data...")
    df_raw = pd.read_excel('backtest_super_patterns_stocks.xlsx', sheet_name=0)
    
    df_names = pd.read_sql("SELECT DISTINCT stock_code, stock_name FROM industry.theme_name_list", conn)
    name_to_code = dict(zip(df_names['stock_name'], df_names['stock_code']))
    
    results = []
    
    print(f"Applying filters (Volume Spike >= 1.8, Smart Money >= 130,000, 20MA Disparity <= 120, RSI(14) <= 70) to {len(df_raw)} stocks...")
    
    for idx, row in df_raw.iterrows():
        dt = row['Signal Date']
        sc = name_to_code.get(row['Stock Name'])
        
        if not sc:
            continue
            
        q_price = f"""
            SELECT v1.date, v1.open, v1.close, v1.trade_value, v1.ma20, v2.rsi
            FROM visual.vsl_anly_stocks_price_subindex01 v1
            JOIN visual.vsl_anly_stocks_price_subindex02 v2 ON v1.stock_code = v2.stock_code AND v1.date = v2.date
            WHERE v1.stock_code = '{sc}' AND v1.date <= '{dt}' 
            ORDER BY v1.date DESC LIMIT 40
        """
        df_p = pd.read_sql(q_price, conn)
        
        if len(df_p) < 21:
            continue
            
        df_p = df_p.sort_values('date').reset_index(drop=True)
        
        # 20일 이격도 계산 (DB에 저장된 ma20 활용)
        df_p['disparity_20'] = (df_p['close'] / df_p['ma20']) * 100
        
        # 거래대금 스파이크 (당일 / 과거 20일 평균)
        df_p['avg_trade_value_20'] = df_p['trade_value'].shift(1).rolling(20).mean()
        df_p['volume_spike'] = df_p['trade_value'] / df_p['avg_trade_value_20']
        
        # 당일 데이터
        d_day_data = df_p.iloc[-1]
        vol_spike = d_day_data['volume_spike']
        rsi = d_day_data['rsi']
        disparity = d_day_data['disparity_20']
        open_price = d_day_data['open'] if 'open' in d_day_data else np.nan
        close_price = d_day_data['close']
        
        # 필터링 조건
        if pd.isna(vol_spike) or vol_spike < 1.8:
            continue
            
        if pd.isna(rsi) or rsi > 70 or rsi < 30:
            continue
            
        if pd.isna(disparity) or disparity > 120:
            continue
            
        if pd.notna(open_price) and open_price > 0:
            if close_price >= open_price * 1.10:
                continue
            
        # 2. Smart Money Flow (최근 3일 합산)
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
        row_dict['20MA Disparity (%)'] = round(disparity, 2)
        row_dict['RSI(14)'] = round(rsi, 2)
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
    
    sort_order = {
        '6등급 -> 4등급 -> 1등급': 1, 
        '4등급 -> 3등급 -> 1등급': 2, 
        '4등급 -> 2등급 -> 2등급': 3,
        '3등급 -> 2등급 -> 1등급': 4,
        '3등급 -> 3등급 -> 1등급': 5
    }
    summary['sort_key'] = summary['테마 패턴'].map(sort_order).fillna(99)
    summary = summary.sort_values('sort_key').drop(columns='sort_key')
    
    # Save to Excel
    excel_path = 'backtest_super_patterns_filtered_v3.xlsx'
    with pd.ExcelWriter(excel_path) as writer:
        df_filtered.to_excel(writer, sheet_name='Raw Data', index=False)
        summary.to_excel(writer, sheet_name='Summary', index=False)
        
    print(f"Filtered raw {len(df_raw)} stocks down to {len(df_filtered)} highly probable stocks.")
    print("\n=== V3 Filter Summary ===")
    print(summary.to_string(index=False))
    print(f"\nSaved to {excel_path} with 2 sheets.")
    
    conn.close()

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    main()
