import os
import psycopg2
import pandas as pd
import numpy as np

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
    
    print("Loading backtest results...")
    df_raw = pd.read_excel('backtest_super_patterns_stocks.xlsx', sheet_name='Raw Data')
    
    # 필터: 6등급 -> 4등급 -> 1등급
    df_target = df_raw[df_raw['Pattern'] == '6등급 -> 4등급 -> 1등급'].copy()
    
    # 결과를 담을 리스트
    analysis_results = []
    
    print(f"Analyzing {len(df_target)} stocks for Winner/Loser features...")
    
    df_names = pd.read_sql("SELECT DISTINCT stock_code, stock_name FROM industry.theme_name_list", conn)
    name_to_code = dict(zip(df_names['stock_name'], df_names['stock_code']))
    
    for idx, row in df_target.iterrows():
        dt = row['Signal Date']
        sc = name_to_code.get(row['Stock Name'])
        
        if not sc:
            continue
        
        # 1. 가격/거래대금 데이터 40일치 조회 (RSI, MA 계산용)
        q_price = f"""
            SELECT date, close, trade_value 
            FROM visual.vsl_anly_stocks_price_subindex01 
            WHERE stock_code = '{sc}' AND date <= '{dt}' 
            ORDER BY date DESC LIMIT 40
        """
        df_p = pd.read_sql(q_price, conn)
        
        if len(df_p) < 20:
            continue
            
        df_p = df_p.sort_values('date').reset_index(drop=True)
        
        # RSI 계산
        df_p['rsi'] = calc_rsi(df_p['close'], 14)
        
        # 20일 이평 및 이격도
        df_p['ma20'] = df_p['close'].rolling(20).mean()
        df_p['disparity_20'] = (df_p['close'] / df_p['ma20']) * 100
        
        # 거래대금 폭증 (당일 / 과거 20일 평균)
        df_p['avg_trade_value_20'] = df_p['trade_value'].shift(1).rolling(20).mean()
        df_p['volume_spike'] = df_p['trade_value'] / df_p['avg_trade_value_20']
        
        # D-day 데이터 추출
        d_day_data = df_p.iloc[-1]
        rsi = d_day_data['rsi']
        disparity = d_day_data['disparity_20']
        vol_spike = d_day_data['volume_spike']
        
        # 2. 수급 데이터 (D-2 ~ D-day 3일간 합산)
        q_flow = f"""
            SELECT SUM(CASE WHEN investor IN ('기관합계', '외국인') THEN net_trade_vol ELSE 0 END) as smart_money
            FROM visual.vsl_krx_stocks_investor_shares_trading_info
            WHERE stock_code = '{sc}' AND date <= '{dt}' 
            AND date >= (SELECT MIN(date) FROM (SELECT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date <= '{dt}' GROUP BY date ORDER BY date DESC LIMIT 3) t)
        """
        df_f = pd.read_sql(q_flow, conn)
        smart_money = df_f.iloc[0]['smart_money'] if not df_f.empty else 0
        
        # 승패 기준: 수익 여부 (D+5 종가 기준 0% 이상이면 Winner)
        is_winner = 'Winner(수익)' if row['D+5 Return (%)'] > 0 else 'Loser(손실)'
        
        analysis_results.append({
            'Signal Date': dt,
            'Stock Name': row['Stock Name'],
            'Theme': row['Theme'],
            'Winner/Loser': is_winner,
            'D+5 Return (%)': row['D+5 Return (%)'],
            'Max 5-Day Return (%)': row['Max 5-Day Return (%)'],
            'RSI(14)': round(rsi, 2) if pd.notna(rsi) else np.nan,
            '20MA Disparity (%)': round(disparity, 2) if pd.notna(disparity) else np.nan,
            'Volume Spike (Times)': round(vol_spike, 2) if pd.notna(vol_spike) else np.nan,
            'Smart Money Flow (3 Days)': smart_money
        })
        
    df_res = pd.DataFrame(analysis_results)
    
    # 엑셀 저장
    excel_path = 'winner_loser_analysis.xlsx'
    df_res.to_excel(excel_path, index=False)
    
    # 요약 통계 산출
    summary = df_res.groupby('Winner/Loser').agg(
        Count=('Stock Name', 'count'),
        Avg_RSI=('RSI(14)', 'mean'),
        Avg_20MA_Disparity=('20MA Disparity (%)', 'mean'),
        Avg_Volume_Spike=('Volume Spike (Times)', 'mean'),
        Avg_Smart_Money=('Smart Money Flow (3 Days)', 'mean')
    ).round(2).reset_index()
    
    print("\n=== Winner vs Loser Feature Summary ===")
    print(summary.to_string(index=False))
    print(f"\nSaved detailed analysis to {excel_path}")
    
    conn.close()

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    main()
