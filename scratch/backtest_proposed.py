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

# 1. 2025-04-01 기준 종목 선정 (제안된 새로운 가중치 적용)
def get_top_stocks_on_date(target_date):
    conn = get_connection()
    
    # 제안된 새로운 가중치 (Value 35%, Profit 25%, Senti 15%, Vol 25%)
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
        WHERE date >= (SELECT max_date - INTERVAL '8 months' FROM latest_date)
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
                roe,
                'KOSPI' AS market_type
            FROM company.kis_kospi_info
            UNION ALL
            SELECT 
                shortcode AS stock_code, 
                roe,
                'KOSDAQ' AS market_type
            FROM company.kis_kosdaq_info
        ) k ON s1.stock_code = k.stock_code
        WHERE s1.date = (SELECT max_date FROM latest_date)
    ),
    sentiment_data AS (
        SELECT 
            date,
            stock_code,
            invest_senti
        FROM visual.vsl_anly_stocks_price_subindex03
        WHERE date = (SELECT max_date FROM latest_date)
    ),
    analyst_data AS (
        SELECT 
            code AS stock_code,
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
        SELECT 
            b.*,
            COALESCE(s.invest_senti, 0) AS invest_senti,
            COALESCE(a.has_sell_opinion, 0) AS has_sell_opinion
        FROM base_data b
        LEFT JOIN sentiment_data s ON b.stock_code = s.stock_code
        LEFT JOIN analyst_data a ON b.stock_code = a.stock_code
    ),
    final_scoring AS (
        SELECT 
            *,
            (PERCENT_RANK() OVER (ORDER BY roe ASC)) * 100 AS roe_rank_score,
            (PERCENT_RANK() OVER (ORDER BY invest_senti ASC)) * 100 AS senti_rank_score,
            (PERCENT_RANK() OVER (ORDER BY vol_momentum ASC)) * 100 AS vol_rank_score,
            (PERCENT_RANK() OVER (PARTITION BY wics_name ORDER BY pbr DESC)) * 100 AS industry_rel_pbr_score
        FROM scoring_base
        WHERE pbr > 0 AND pbr < 10
          AND has_sell_opinion != 1
    )
    SELECT 
        date,
        wics_name,
        stock_code,
        stock_name,
        ROUND(
            (
                (industry_rel_pbr_score * 0.35) + 
                (roe_rank_score * 0.25) + 
                (senti_rank_score * 0.15) +
                (vol_rank_score * 0.25)
            )::numeric
        , 2) AS total_score,
        ROW_NUMBER() OVER(PARTITION BY wics_name ORDER BY (
            (industry_rel_pbr_score * 0.35) + 
            (roe_rank_score * 0.25) + 
            (senti_rank_score * 0.15) +
            (vol_rank_score * 0.25)
        ) DESC) as industry_rank
    FROM final_scoring
    WHERE TRUE
    ORDER BY wics_name, industry_rank
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df[df['industry_rank'] <= 3]

# 2. 특정 시점들의 가격 조회 함수
def get_prices(stock_codes, date_list):
    conn = get_connection()
    placeholders = ', '.join(['%s'] * len(stock_codes))
    
    results = []
    for target_date in date_list:
        query = f"""
        SELECT stock_code, date, close
        FROM (
            SELECT stock_code, date, close,
                   ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY date ASC) as rn
            FROM visual.vsl_anly_stocks_price_subindex01
            WHERE stock_code IN ({placeholders})
              AND date >= %s
        ) t
        WHERE rn = 1
        """
        df = pd.read_sql_query(query, conn, params=(*stock_codes, target_date))
        df['target_date'] = target_date
        results.append(df)
    
    conn.close()
    return pd.concat(results)

# 3. 메인 백테스트 실행
def run_backtest():
    base_date = '2025-04-01'
    print(f"[{base_date}] 기준 새로운 가중치로 상위 종목 추출 중...")
    top_stocks = get_top_stocks_on_date(base_date)
    
    if top_stocks.empty:
        print("상위 종목 데이터가 없습니다.")
        return

    codes = top_stocks['stock_code'].unique().tolist()
    target_dates = [base_date, '2025-07-01', '2025-10-01', '2026-01-01', '2026-04-01']
    
    print("히스토리컬 가격 데이터 조회 중...")
    prices = get_prices(codes, target_dates)
    price_pivot = prices.pivot(index='stock_code', columns='target_date', values='close')
    
    backtest_result = top_stocks.merge(price_pivot, on='stock_code', how='left')
    periods = [('3개월', '2025-07-01'), ('6개월', '2025-10-01'), ('9개월', '2026-01-01'), ('12개월', '2026-04-01')]
    
    for label, target in periods:
        backtest_result[label] = (backtest_result[target] - backtest_result[base_date]) / backtest_result[base_date] * 100

    final_cols = ['wics_name', 'stock_code', 'stock_name', 'total_score', 'industry_rank', '3개월', '6개월', '9개월', '12개월']
    summary = backtest_result[final_cols]
    
    industry_avg = summary.groupby('wics_name')[['3개월', '6개월', '9개월', '12개월']].mean()
    total_avg = summary[['3개월', '6개월', '9개월', '12개월']].mean()
    
    print("\n=== [새로운 제안 가중치] 전체 평균 수익률 추이 ===")
    print(total_avg)
    
    # 상위 5개 업종 (12개월 기준)
    top_5_industries = industry_avg.sort_values(by='12개월', ascending=False).head(5)
    print("\n=== [새로운 제안 가중치] 수익률 상위 5개 업종 (12개월) ===")
    print(top_5_industries)
    
    summary.to_csv('backtest_result_proposed_weights.csv', index=False, encoding='utf-8-sig')
    industry_avg.to_csv('industry_avg_proposed_weights.csv', encoding='utf-8-sig')
    
    return summary, total_avg, top_5_industries

if __name__ == "__main__":
    run_backtest()
