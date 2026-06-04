import os
import psycopg2
import pandas as pd
import datetime

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def get_sector_data(target_date):
    """지정된 날짜 시점에서 각 업종의 가성비 점수 계산"""
    conn = get_connection()
    
    # 1. 시점별 PBR 데이터 (KRX)
    query_pbr = f"""
    SELECT code as stock_code, pbr
    FROM company.krx_stocks_fundamental_info
    WHERE date = (SELECT MAX(date) FROM company.krx_stocks_fundamental_info WHERE date <= '{target_date}')
    """
    df_pbr = pd.read_sql_query(query_pbr, conn)
    
    # 2. 시점별 ROE 데이터 (금융 분기 팩터)
    # est_dt가 공시일(또는 추정일)이므로 해당 시점 이전에 공시된 가장 최신 데이터를 사용
    query_roe = f"""
    SELECT stock_code, roe
    FROM (
        SELECT stock_code, roe, 
               ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY est_dt DESC) as rn
        FROM company.financial_factor_quarterly
        WHERE est_dt < '{target_date}' AND roe IS NOT NULL AND roe > 0
    ) t WHERE rn = 1
    """
    df_roe = pd.read_sql_query(query_roe, conn)
    
    # 3. 업종 매핑 (WICS)
    query_wics = f"""
    SELECT DISTINCT stock_code, wics_name
    FROM visual.vsl_anly_stocks_price_subindex01
    WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01 WHERE date <= '{target_date}')
    """
    df_wics = pd.read_sql_query(query_wics, conn)
    
    conn.close()
    
    # 데이터 결합
    df = pd.merge(df_wics, df_pbr, on='stock_code')
    df = pd.merge(df, df_roe, on='stock_code')
    
    # 업종별 중앙값 계산
    sector_stats = df.groupby('wics_name').agg({
        'roe': 'median',
        'pbr': 'median',
        'stock_code': 'count'
    }).rename(columns={'stock_code': 'company_count'})
    
    # 효율성 점수 (ROE / PBR)
    sector_stats['efficiency'] = sector_stats['roe'] / sector_stats['pbr']
    
    return sector_stats.sort_values('efficiency', ascending=False)

def calculate_returns(sectors, start_date, duration_months):
    """지정된 업종들의 수익률 계산 (종목별 종가 평균 기준)"""
    conn = get_connection()
    
    end_date = pd.to_datetime(start_date) + pd.DateOffset(months=duration_months)
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # 해당 섹터에 속한 종목들의 시작과 끝 종가 가져오기
    query = f"""
    SELECT wics_name, stock_code, date, close
    FROM (
        SELECT wics_name, stock_code, date, close,
               ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY ABS(date - CAST('{start_date}' AS DATE))) as rn_start,
               ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY ABS(date - CAST('{end_date_str}' AS DATE))) as rn_end
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE wics_name IN %s
    ) t
    WHERE rn_start = 1 OR rn_end = 1
    """
    df = pd.read_sql_query(query, conn, params=(tuple(sectors),))
    conn.close()
    
    results = {}
    for sector in sectors:
        sector_df = df[df['wics_name'] == sector]
        
        # 각 종목별로 시작일과 종료일 데이터가 모두 있는 것만 필터링
        returns = []
        for code in sector_df['stock_code'].unique():
            stock_data = sector_df[sector_df['stock_code'] == code].sort_values('date')
            if len(stock_data) >= 2:
                start_p = stock_data.iloc[0]['close']
                end_p = stock_data.iloc[-1]['close']
                if start_p > 0:
                    returns.append(end_p / start_p - 1)
        
        if returns:
            results[sector] = (sum(returns) / len(returns)) * 100 # 평균 수익률
        else:
            results[sector] = None
    return results

def run_backtest():
    test_dates = ['2024-01-02', '2025-01-02']
    
    final_results = []
    
    for start_date in test_dates:
        print(f"\n--- Backtesting for Start Date: {start_date} ---")
        efficiency_rank = get_sector_data(start_date)
        top_5 = efficiency_rank.head(5)
        top_5_names = top_5.index.tolist()
        
        print(f"Top 5 Sectors: {', '.join(top_5_names)}")
        
        # 6개월 수익률
        ret_6m = calculate_returns(top_5_names, start_date, 6)
        # 12개월 수익률 (2025년의 경우 현재까지 - 약 15개월)
        ret_12m = calculate_returns(top_5_names, start_date, 12)
        
        for sector in top_5_names:
            final_results.append({
                'base_year': start_date[:4],
                'sector': sector,
                'roe': top_5.loc[sector, 'roe'],
                'pbr': top_5.loc[sector, 'pbr'],
                'efficiency': top_5.loc[sector, 'efficiency'],
                'return_6m': ret_6m.get(sector),
                'return_12m': ret_12m.get(sector)
            })
            
    df_res = pd.DataFrame(final_results)
    df_res.to_csv(r'c:\Users\Hubnet\antigravity\results\backtest_fundamental_efficiency_results.csv', index=False, encoding='utf-8-sig')
    print("\nBacktest Results Saved to results/backtest_fundamental_efficiency_results.csv")
    print(df_res)

if __name__ == "__main__":
    run_backtest()
