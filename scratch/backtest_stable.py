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

# 1. 선정 함수 (가중치를 파라미터로 받음)
def get_top_stocks(target_date, w_val, w_prof, w_senti, w_vol):
    conn = get_connection()
    query = f"""
    WITH latest_date AS ( SELECT '{target_date}'::date AS max_date ),
    volume_stats AS (
        SELECT stock_code, date, volume,
            AVG(volume) OVER (PARTITION BY stock_code ORDER BY date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS vol_last_1w,
            AVG(volume) OVER (PARTITION BY stock_code ORDER BY date ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) AS vol_12w_avg
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date >= (SELECT max_date - INTERVAL '8 months' FROM latest_date)
    ),
    base_data AS (
        SELECT s1.date, s1.stock_code, s1.stock_name, s1.wics_name, f.pbr, f.per, COALESCE(k.roe, 0) AS roe,
            CASE WHEN vs.vol_12w_avg > 0 THEN vs.vol_last_1w / vs.vol_12w_avg ELSE 0 END AS vol_momentum
        FROM visual.vsl_anly_stocks_price_subindex01 s1
        JOIN volume_stats vs ON s1.stock_code = vs.stock_code AND s1.date = vs.date
        LEFT JOIN company.krx_stocks_fundamental_info f ON s1.stock_code = f.code AND s1.date = f.date
        LEFT JOIN (
            SELECT CASE WHEN shortcode LIKE 'F%' THEN SUBSTRING(shortcode, 2) ELSE shortcode END AS stock_code, roe FROM company.kis_kospi_info
            UNION ALL SELECT shortcode AS stock_code, roe FROM company.kis_kosdaq_info
        ) k ON s1.stock_code = k.stock_code
        WHERE s1.date = (SELECT max_date FROM latest_date)
    ),
    sentiment_data AS (
        SELECT date, stock_code, invest_senti FROM visual.vsl_anly_stocks_price_subindex03 WHERE date = (SELECT max_date FROM latest_date)
    ),
    analyst_data AS (
        SELECT code AS stock_code, MAX(CASE WHEN inv_opi IN ('시장평균', 'Hold', '중립', 'MarketPerform', '투자의견없음', '없음', 'Neutral', '매도', 'Sell', 'UnderPerform', 'MarketUnderPerform', '시장수익률하회', '비중축소', 'Reduce') THEN 1 ELSE 0 END) AS has_sell_opinion
        FROM llm.naver_stock_report WHERE date >= (SELECT max_date - INTERVAL '3 months' FROM latest_date) GROUP BY code
    ),
    scoring_base AS (
        SELECT b.*, COALESCE(s.invest_senti, 0) AS invest_senti, COALESCE(a.has_sell_opinion, 0) AS has_sell_opinion FROM base_data b
        LEFT JOIN sentiment_data s ON b.stock_code = s.stock_code LEFT JOIN analyst_data a ON b.stock_code = a.stock_code
    ),
    final_scoring AS (
        SELECT *, (PERCENT_RANK() OVER (ORDER BY roe ASC)) * 100 AS roe_rank_score, (PERCENT_RANK() OVER (ORDER BY invest_senti ASC)) * 100 AS senti_rank_score, (PERCENT_RANK() OVER (ORDER BY vol_momentum ASC)) * 100 AS vol_rank_score, (PERCENT_RANK() OVER (PARTITION BY wics_name ORDER BY pbr DESC)) * 100 AS industry_rel_pbr_score
        FROM scoring_base WHERE pbr > 0 AND pbr < 10 AND has_sell_opinion != 1
    )
    SELECT wics_name, stock_code, stock_name,
        ROUND(((industry_rel_pbr_score * {w_val}) + (roe_rank_score * {w_prof}) + (senti_rank_score * {w_senti}) + (vol_rank_score * {w_vol}))::numeric, 2) AS total_score,
        ROW_NUMBER() OVER(PARTITION BY wics_name ORDER BY ((industry_rel_pbr_score * {w_val}) + (roe_rank_score * {w_prof}) + (senti_rank_score * {w_senti}) + (vol_rank_score * {w_vol})) DESC) AS industry_rank
    FROM final_scoring
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df[df['industry_rank'] <= 3]

def get_prices(codes, dates):
    conn = get_connection()
    results = []
    placeholders = ', '.join(['%s'] * len(codes))
    for d in dates:
        q = f"SELECT stock_code, date, close FROM (SELECT stock_code, date, close, ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY date ASC) as rn FROM visual.vsl_anly_stocks_price_subindex01 WHERE stock_code IN ({placeholders}) AND date >= %s) t WHERE rn = 1"
        res = pd.read_sql_query(q, conn, params=(*codes, d))
        res['req_date'] = d
        results.append(res)
    conn.close()
    return pd.concat(results).pivot(index='stock_code', columns='req_date', values='close')

def run_compare(target_date, label_prefix, w_val, w_prof, w_senti, w_vol):
    print(f"[{target_date}] {label_prefix} 가중치로 백테스트 진행 중...")
    stocks = get_top_stocks(target_date, w_val, w_prof, w_senti, w_vol)
    
    # 3, 6, 9, 12개월 날짜 계산
    dt = datetime.strptime(target_date, '%Y-%m-%d')
    dates = [target_date]
    for m in [3, 6, 9, 12]:
        dates.append((dt + timedelta(days=m*30.5)).strftime('%Y-%m-%d'))
    
    prices = get_prices(stocks['stock_code'].tolist(), dates)
    merged = stocks.merge(prices, on='stock_code', how='left')
    
    returns = []
    for i in range(1, 5):
        ret = (merged[dates[i]] - merged[dates[0]]) / merged[dates[0]] * 100
        returns.append(ret.mean())
    return returns

if __name__ == "__main__":
    # 안정형 가중치: 가치 50%, 수익성 30%, 심리 10%, 수급 10%
    WV, WP, WS, WM = 0.50, 0.30, 0.10, 0.10
    
    # 1. 횡보장 (2024-02-01)
    res_sideways = run_compare('2024-02-01', '안정형', WV, WP, WS, WM)
    
    # 2. 강세장 (2025-04-01)
    res_bull = run_compare('2025-04-01', '안정형', WV, WP, WS, WM)
    
    print("\n=== [안정형 가중치] 백테스트 결과 (가치 50%, 수익성 30%) ===")
    print(f"횡보장(2024-02): 3M: {res_sideways[0]:.2f}%, 6M: {res_sideways[1]:.2f}%, 9M: {res_sideways[2]:.2f}%, 12M: {res_sideways[3]:.2f}%")
    print(f"강세장(2025-04): 3M: {res_bull[0]:.2f}%, 6M: {res_bull[1]:.2f}%, 9M: {res_bull[2]:.2f}%, 12M: {res_bull[3]:.2f}%")
