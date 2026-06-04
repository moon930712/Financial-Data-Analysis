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

# PER 기반 종목 선정 로직 (적자 기업 포함)
def get_top_stocks_on_date(target_date):
    conn = get_connection()
    
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
    report_stats AS (
        SELECT 
            code AS stock_code,
            COUNT(*) AS report_count
        FROM llm.naver_stock_report
        WHERE date BETWEEN (SELECT '{target_date}'::date - INTERVAL '30 days') AND '{target_date}'::date
        GROUP BY code
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
            CASE WHEN vs.vol_12w_avg > 0 THEN vs.vol_last_1w / vs.vol_12w_avg ELSE 0 END AS vol_momentum,
            COALESCE(r.report_count, 0) AS report_count
        FROM visual.vsl_anly_stocks_price_subindex01 s1
        JOIN volume_stats vs ON s1.stock_code = vs.stock_code AND s1.date = vs.date
        LEFT JOIN report_stats r ON s1.stock_code = r.stock_code
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
        WHERE date >= (SELECT '{target_date}'::date - INTERVAL '1 months')
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
            (PERCENT_RANK() OVER (ORDER BY report_count ASC)) * 100 AS report_rank_score,
            (PERCENT_RANK() OVER (PARTITION BY wics_name ORDER BY (CASE WHEN per > 0 THEN per ELSE 999999 END) DESC)) * 100 AS industry_rel_per_score
        FROM scoring_base
        WHERE has_sell_opinion != 1
    ),
    ranked AS (
        SELECT 
            date,
            wics_name,
            stock_code,
            stock_name,
            per,
            roe,
            report_count,
            ROUND(
                (
                    (industry_rel_per_score * 0.2) + 
                    (roe_rank_score * 0.2) + 
                    (vol_rank_score * 0.3) +
                    (senti_rank_score * 0.1) +
                    (report_rank_score * 0.2)
                )::numeric
            , 2) AS total_score,
            ROW_NUMBER() OVER(PARTITION BY wics_name ORDER BY (
                (industry_rel_per_score * 0.2) + 
                (roe_rank_score * 0.2) + 
                (vol_rank_score * 0.3) +
                (senti_rank_score * 0.1) +
                (report_rank_score * 0.2)
            ) DESC) as industry_rank
        FROM final_scoring
    )
    SELECT * FROM ranked WHERE industry_rank <= 3
    ORDER BY wics_name, industry_rank
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_prices(stock_codes, date_list):
    conn = get_connection()
    if not stock_codes:
        return pd.DataFrame()
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
    return pd.concat(results) if results else pd.DataFrame()

def run_backtest(base_date, suffix):
    print(f"\n--- [{base_date}] [{suffix}] 백테스트 시작 ---")
    top_stocks = get_top_stocks_on_date(base_date)
    if top_stocks.empty:
        print("상위 종목 데이터가 없습니다.")
        return
    
    codes = top_stocks['stock_code'].unique().tolist()
    d = datetime.strptime(base_date, '%Y-%m-%d')
    target_dates = [base_date]
    for m in [3, 6, 9, 12]:
        future_date = (d + timedelta(days=m*30.5)).strftime('%Y-%m-%d')
        target_dates.append(future_date)
    
    print("가격 데이터 조회 중...")
    prices = get_prices(codes, target_dates)
    if prices.empty:
        print("가격 데이터가 없습니다.")
        return

    price_pivot = prices.pivot(index='stock_code', columns='target_date', values='close')
    backtest_result = top_stocks.merge(price_pivot, on='stock_code', how='left')
    
    actual_dates = sorted(price_pivot.columns.tolist())
    base_col = actual_dates[0]
    
    perf_cols = []
    for i, target in enumerate(actual_dates[1:]):
        label = f"{(i+1)*3}개월"
        backtest_result[label] = (backtest_result[target] - backtest_result[base_col]) / backtest_result[base_col] * 100
        perf_cols.append(label)

    summary = backtest_result[['wics_name', 'stock_code', 'stock_name', 'per', 'roe', 'report_count', 'total_score'] + perf_cols]
    total_avg = summary[perf_cols].mean()
    
    print(f"=== [{suffix}] 전체 평균 수익률 ===")
    print(total_avg)
    
    summary.to_csv(f'backtest_per_{suffix}.csv', index=False, encoding='utf-8-sig')
    return total_avg

if __name__ == "__main__":
    # 2024년 횡보장
    run_backtest('2024-02-01', 'sideways_2024')
    # 2025년 강세장
    run_backtest('2025-04-01', 'bull_2025')
