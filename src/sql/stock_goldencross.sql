-- 테마별 MACD 골든크로스 신호 발생 종목 상세 리스트
-- 작성일: 2026-04-16
WITH histo_base AS (
    -- 1. MACD 히스토그램 데이터 산출
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
signals AS (
    -- 2. 골든크로스 신호 필터링 (전일 음수 -> 당일 양수 전환)
    SELECT 
        * 
    FROM histo_base
    WHERE 1=1
      AND date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02)
      AND lag_histogram < 0
      AND histogram >= 0
),
stock_info AS (
    -- 3. 시가총액 정보 결합
    SELECT shortcode, marketcap FROM company.kis_kospi_info
    UNION ALL
    SELECT shortcode, previousdaymarketcap as marketcap FROM company.kis_kosdaq_info
),
themed_signals AS (
    -- 4. 네이버 테마 정보 및 시총 결합 (SPAC 제외)
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
    -- 5. 테마별 집계 (종목 수 DESC, 시총 합계 DESC)
    SELECT 
        theme_name
        , COUNT(*) as signal_count
        , SUM(marketcap) as theme_signal_mcap_sum
        , MAX(date) as date
    FROM themed_signals
    GROUP BY theme_name
)
-- 6. 최종 출력: 테마별 골든크로스 종목 상세 (시총순 정렬)
SELECT 
    to_char(ts.date, 'YYYY-MM-DD') as "날짜"
    , tr.theme_name as "업종명"
    , ts.stock_name as "종목명"
--    , ts.stock_code as "종목코드"
--    , ts.marketcap as "시가총액"
--    , tr.signal_count as "종목수"
FROM theme_ranking tr
JOIN themed_signals ts ON tr.theme_name = ts.theme_name
WHERE 1=1
  AND tr.theme_name IN ($industry_gc)
ORDER BY 
    tr.signal_count DESC
    , tr.theme_signal_mcap_sum DESC
    , tr.theme_name ASC
    , ts.marketcap DESC;
