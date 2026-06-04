-- 업종 순환매 마스터 종목 상세 리스트 (현황판 연동용)
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
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
histo_stats AS (
    -- 2. 보조 지표 (평균, 표준편차) 산출
    SELECT 
        * 
        , AVG(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_avg_20
        , STDDEV(lag_histogram) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hist_std_20
    FROM histo_base
),
signals AS (
    -- 3. 4가지 핵심 신호 식별 (Z-Score 1.0 기준)
    SELECT 
        s.date
        , s.stock_code
        , s.stock_name
        , CASE WHEN s.histogram < 0 AND s.lag2_histogram > s.lag_histogram 
          AND s.lag_histogram < s.histogram 
          AND (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) <= -1.0 THEN 1 ELSE 0 END as low_signal
        , CASE WHEN s.lag_histogram < 0 AND s.histogram >= 0 THEN 1 ELSE 0 END as gc_signal
        , CASE WHEN s.histogram > 0 AND s.lag2_histogram < s.lag_histogram 
          AND s.lag_histogram > s.histogram 
          AND (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) >= 1.0 THEN 1 ELSE 0 END as high_signal
        , CASE WHEN s.lag_histogram > 0 AND s.histogram <= 0 THEN 1 ELSE 0 END as dc_signal
    FROM histo_stats s
    WHERE 1=1
      AND s.date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02)
),
stock_info AS (
    -- 4. 시가총액 정보 결합
    SELECT shortcode, marketcap FROM company.kis_kospi_info
    UNION ALL
    SELECT shortcode, previousdaymarketcap as marketcap FROM company.kis_kosdaq_info
),
themed_signals AS (
    -- 5. 네이버 테마 정보 결합 (신호가 있는 종목만 추출)
    SELECT 
        s.date
        , nt.theme_name
        , s.stock_name
        , s.stock_code
        , COALESCE(si.marketcap, 0) as marketcap
        , CASE 
            WHEN s.low_signal = 1 THEN 'MACD음수맥스'
            WHEN s.gc_signal = 1 THEN '골든크로스'
            WHEN s.high_signal = 1 THEN 'MACD양수맥스'
            WHEN s.dc_signal = 1 THEN '데드크로스'
            ELSE NULL 
          END as macd_status
    FROM signals s
    JOIN company.naver_theme nt ON s.stock_code = nt.stock_code
    LEFT JOIN stock_info si ON s.stock_code = si.shortcode
    WHERE 1=1
      AND (s.low_signal + s.gc_signal + s.high_signal + s.dc_signal) > 0
      AND nt.theme_name != '기업인수목적회사(SPAC)'
)
-- 6. 최종 출력 (업종명 추가 및 시총 정렬 유지)
SELECT 
    to_char(ts.date, 'YYYY-MM-DD') as "날짜"
    , ts.theme_name as "업종명"
    , ts.stock_name as "종목명"
    , ts.macd_status as "MACD상태"
FROM themed_signals ts
WHERE 1=1
--  AND ts.theme_name IN ($industry_master)
ORDER BY 
    ts.marketcap DESC -- 시총이 큰 종목부터 출력
    , ts.stock_name ASC;
