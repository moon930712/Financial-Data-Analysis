-- 테마별 MACD 히스토그램 바닥 반등(Bottoming) 신호 분석
-- 작성일: 2026-04-16
WITH histo_base AS (
    -- 1. 기본 히스토그램 및 Lag 데이터 산출
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        , LAG(m.macd - m.signal, 2) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag2_histogram
        , m.rsi
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
histo_stats AS (
    -- 2. 보조 지표 (평균, 표준편차, 최저치, 과거 고점) 산출
    SELECT 
        * 
        , AVG(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_avg_20
        , STDDEV(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_std_20
--        , MIN(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS hist_lowest_14
--        , MAX(histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 60 PRECEDING AND 10 PRECEDING) AS max_hist_past
    FROM histo_base
),
signals AS (
    -- 3. 바닥 반등 신호 필터링 (사용자 정의 산식)
    SELECT 
        s.*
        , (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) AS z_score
    FROM histo_stats s
    WHERE 1=1
      AND s.date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02)
      AND s.histogram < 0
      AND s.lag2_histogram > s.lag_histogram
      AND s.lag_histogram < s.histogram
      AND (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) <= -1.0
--      AND s.max_hist_past > 0
--      AND s.max_hist_past >= ABS(s.hist_lowest_14) * 1.2
),
stock_info AS (
    -- 4. 시가총액 정보 결합
    SELECT shortcode, marketcap FROM company.kis_kospi_info
    UNION ALL
    SELECT shortcode, previousdaymarketcap as marketcap FROM company.kis_kosdaq_info
),
themed_signals AS (
    -- 5. 네이버 테마 정보 및 시총 결합
    SELECT 
        s.date
        , nt.theme_name
        , s.stock_name
        , s.stock_code
        , COALESCE(si.marketcap, 0) as marketcap
    FROM signals s
    JOIN company.naver_theme nt ON s.stock_code = nt.stock_code
    LEFT JOIN stock_info si ON s.stock_code = si.shortcode
    WHERE 1=1
      AND nt.theme_name != '기업인수목적회사(SPAC)'
),
theme_ranking AS (
    -- 6. 테마별 집계 (정합성 기준: 종목 수 DESC, 시총 합계 DESC)
    SELECT 
        theme_name
        , COUNT(*) as signal_count
        , SUM(marketcap) as theme_signal_mcap_sum
        , MAX(date) as date -- 정렬을 위한 날짜 확보
    FROM themed_signals
    GROUP BY theme_name
)
-- 7. 최종 출력: 테마 순위에 따른 종목 상세 리스트
SELECT 
    to_char(tr.date, 'YYYY-MM-DD') as "날짜"
    , tr.theme_name as "업종명"
    , ts.stock_name as "종목명"
--    , ts.stock_code
--    , ts.marketcap
    , tr.signal_count as "업종내신호수"
--    , ROUND(tr.theme_signal_mcap_sum::numeric, 0) as "업종신호시총합(억)"
FROM theme_ranking tr
JOIN themed_signals ts ON tr.theme_name = ts.theme_name
WHERE 1=1
  AND tr.theme_name IN ($industry_low)
ORDER BY 
    tr.signal_count DESC
    , tr.theme_signal_mcap_sum DESC
    , tr.theme_name ASC
    , ts.marketcap DESC;
