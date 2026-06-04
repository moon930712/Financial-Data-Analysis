import os
import psycopg2
import pandas as pd
from datetime import datetime, timedelta

# DB 연결 및 환경 변수 로드
def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    try:
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip()
                    except: pass

load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

# 1. 2024-02-01 기준 종목 선정 (최적 가중치 적용)
def get_top_stocks_on_date(target_date):
    conn = get_connection()
    # 최적화된 가중치 (Value 35%, Profit 25%, Senti 15%, Vol 25%)
    query = f"""
    WITH latest_date AS (
        SELECT '{target_date}'::date AS max_date 
    ),
    volume_stats AS (
        SELECT 
            stock_code,
            date,
            volume,
            AVG(volume) OVER (PARTITION BY stock_code ORDER BY date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS vol_last_1w,
            AVG(volume) OVER (PARTITION BY stock_code ORDER BY date ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) AS vol_12w_avg
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= (SELECT max_date - INTERVAL '6 months' FROM latest_date)
    ),
    base_data AS (
        SELECT 
            s1.date,
            s1.stock_code,
            s1.stock_name,
            s1.wics_name,
            f.pbr,
            f.per,
            COALESCE(k.roe, 0) AS roe,
            k.market_type,
            CASE WHEN vs.vol_12w_avg > 0 THEN vs.vol_last_1w / vs.vol_12w_avg ELSE 0 END AS vol_momentum
        FROM visual.vsl_anly_stocks_price_subindex01 s1
        JOIN volume_stats vs ON s1.stock_code = vs.stock_code AND s1.date = vs.date
        LEFT JOIN company.krx_stocks_fundamental_info f ON s1.stock_code = f.code AND s1.date = f.date
        LEFT JOIN (
            SELECT 
                CASE WHEN shortcode LIKE 'F%' THEN SUBSTRING(shortcode, 2) ELSE shortcode END AS stock_code,
                roe, 'KOSPI' AS market_type
            FROM company.kis_kospi_info
            UNION ALL
            SELECT shortcode AS stock_code, roe, 'KOSDAQ' AS market_type
            FROM company.kis_kosdaq_info
        ) k ON s1.stock_code = k.stock_code
        WHERE s1.date = (SELECT max_date FROM latest_date)
    ),
    sentiment_data AS (
        SELECT date, stock_code, invest_senti
        FROM visual.vsl_anly_stocks_price_subindex03
        WHERE date = (SELECT max_date FROM latest_date)
    ),
    analyst_data AS (
        SELECT code AS stock_code,
            MAX(CASE 
                WHEN inv_opi IN ('시장평균', 'Hold', '중립', 'MarketPerform', '투자의견없음', '없음', 'Neutral',
                                 '매도', 'Sell', 'UnderPerform', 'MarketUnderPerform', '시장수익률하회', '비중축소', 'Reduce') THEN 1 
                ELSE 0 
            END) AS has_sell_opinion
        FROM llm.naver_stock_report
        WHERE date >= (SELECT max_date - INTERVAL '3 months' FROM latest_date)
        GROUP BY code
    ),
    scoring_base AS (
        SELECT b.*, COALESCE(s.invest_senti, 0) AS invest_senti, COALESCE(a.has_sell_opinion, 0) AS has_sell_opinion
        FROM base_data b
        LEFT JOIN sentiment_data s ON b.stock_code = s.stock_code
        LEFT JOIN analyst_data a ON b.stock_code = a.stock_code
    ),
    final_scoring AS (
        SELECT *,
            (PERCENT_RANK() OVER (ORDER BY roe ASC)) * 100 AS roe_rank_score,
            (PERCENT_RANK() OVER (ORDER BY invest_senti ASC)) * 100 AS senti_rank_score,
            (PERCENT_RANK() OVER (ORDER BY vol_momentum ASC)) * 100 AS vol_rank_score,
            (PERCENT_RANK() OVER (PARTITION BY wics_name ORDER BY pbr DESC)) * 100 AS industry_rel_pbr_score
        FROM scoring_base
        WHERE pbr > 0 AND pbr < 10 AND has_sell_opinion != 1
    )
    SELECT date, wics_name, stock_code, stock_name,
        ROUND(((industry_rel_pbr_score * 0.35) + (roe_rank_score * 0.25) + (senti_rank_score * 0.15) + (vol_rank_score * 0.25))::numeric, 2) AS total_score,
        ROW_NUMBER() OVER(PARTITION BY wics_name ORDER BY ((industry_rel_pbr_score * 0.35) + (roe_rank_score * 0.25) + (senti_rank_score * 0.15) + (vol_rank_score * 0.25)) DESC) AS industry_rank
    FROM final_scoring
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df[df['industry_rank'] <= 3]

# 2. 벤치마크(전체 시장 평균) 가격 조회
def get_benchmark_prices(date_list):
    conn = get_connection()
    results = []
    for target_date in date_list:
        query = """
        SELECT date, AVG(close) as avg_price
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= %s
        GROUP BY date ORDER BY date LIMIT 1
        """
        results.append(pd.read_sql_query(query, conn, params=(target_date,)))
    conn.close()
    return pd.concat(results)

# 3. 개별 종목 가격 조회
def get_prices(stock_codes, date_list):
    conn = get_connection()
    placeholders = ', '.join(['%s'] * len(stock_codes))
    results = []
    for target_date in date_list:
        query = f"""
        SELECT stock_code, date as actual_date, close FROM (
            SELECT stock_code, date, close, ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY date ASC) as rn
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE stock_code IN ({placeholders}) AND date >= %s
        ) t WHERE rn = 1
        """
        df = pd.read_sql_query(query, conn, params=(*stock_codes, target_date))
        df['req_date'] = target_date
        results.append(df)
    conn.close()
    return pd.concat(results)

def run_sideways_backtest():
    base_date = '2024-02-01'
    print(f"[{base_date}] 기준 횡보장 백테스트 시작...")
    top_stocks = get_top_stocks_on_date(base_date)
    
    target_dates = [base_date, '2024-05-01', '2024-08-01', '2024-11-01', '2025-02-01']
    
    print("시장 벤치마크 데이터 수집 중...")
    bench = get_benchmark_prices(target_dates)
    bench_start = bench.iloc[0]['avg_price']
    bench['cum_return'] = (bench['avg_price'] - bench_start) / bench_start * 100
    
    print("종목별 가격 데이터 수집 중...")
    prices = get_prices(top_stocks['stock_code'].tolist(), target_dates)
    price_pivot = prices.pivot(index='stock_code', columns='req_date', values='close')
    
    merged = top_stocks.merge(price_pivot, on='stock_code', how='left')
    periods = [('3개월', '2024-05-01'), ('6개월', '2024-08-01'), ('9개월', '2024-11-01'), ('12개월', '2025-02-01')]
    
    for label, target in periods:
        merged[label] = (merged[target] - merged[base_date]) / merged[base_date] * 100

    total_avg = merged[['3개월', '6개월', '9개월', '12개월']].mean()
    
    print("\n=== [횡보장 백테스트 결과] ===")
    print(f"기간: {base_date} ~ 2025-02-01")
    report = pd.DataFrame({
        '전략 수익률': total_avg.values,
        '시장 수익률(벤치)': bench['cum_return'].iloc[1:].values
    }, index=['3개월', '6개월', '9개월', '12개월'])
    
    report['초과 수익(Alpha)'] = report['전략 수익률'] - report['시장 수익률(벤치)']
    print(report)
    
    merged.to_csv('backtest_sideways_20240201.csv', index=False, encoding='utf-8-sig')
    report.to_csv('backtest_sideways_summary.csv', encoding='utf-8-sig')
    
    return report

if __name__ == "__main__":
    run_sideways_backtest()
