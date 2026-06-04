-- 업종 순환매 마스터 스코어 분석 (시가총액 가중치 및 표준화 적용)
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
        , CASE WHEN s.histogram < 0 AND s.lag2_histogram > s.lag_histogram AND s.lag_histogram < s.histogram AND (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) <= -1.0 THEN 1 ELSE 0 END as low_signal
        , CASE WHEN s.lag_histogram < 0 AND s.histogram >= 0 THEN 1 ELSE 0 END as gc_signal
        , CASE WHEN s.histogram > 0 AND s.lag2_histogram < s.lag_histogram AND s.lag_histogram > s.histogram AND (s.lag_histogram - s.hist_avg_20) / NULLIF(s.hist_std_20, 0) >= 1.0 THEN 1 ELSE 0 END as high_signal
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
theme_base AS (
    -- 5. 테마별 전체 종목 수 및 시총 합계 산출
    SELECT 
        nt.theme_name
        , COUNT(DISTINCT nt.stock_code) as total_stocks_in_theme
        , SUM(COALESCE(si.marketcap, 0)) as theme_total_mcap
    FROM company.naver_theme nt
    LEFT JOIN stock_info si ON nt.stock_code = si.shortcode
    WHERE 1=1
      AND nt.theme_name != '기업인수목적회사(SPAC)'
    GROUP BY nt.theme_name
),
weighted_signals AS (
    -- 6. 종목별 시총 비중 및 가중치 점수 계산
    SELECT 
        s.date
        , nt.theme_name
        , tb.total_stocks_in_theme
        , s.stock_name
        , COALESCE(si.marketcap, 0) as stock_mcap
        , tb.theme_total_mcap
        -- 신호별 가중치 적용 (Low:+10, GC:+7, High:-5, DC:-10)
        , (s.low_signal * 10 + s.gc_signal * 7 + s.high_signal * -5 + s.dc_signal * -10) as signal_weight
        -- 시총 비중 반영: (종목점수 * (종목시총 / 테마시총))
        , (s.low_signal * 10 + s.gc_signal * 7 + s.high_signal * -5 + s.dc_signal * -10) 
          * (COALESCE(si.marketcap, 0) / NULLIF(tb.theme_total_mcap, 0)) as weighted_score_contrib
        , s.low_signal, s.gc_signal, s.high_signal, s.dc_signal
    FROM signals s
    JOIN company.naver_theme nt ON s.stock_code = nt.stock_code
    JOIN theme_base tb ON nt.theme_name = tb.theme_name
    LEFT JOIN stock_info si ON s.stock_code = si.shortcode
    WHERE 1=1
),
final_aggregation AS (
    -- 7. 테마별 최종 스코어 및 집계 (신호 발생 종목이 3개 이상인 테마만 추출)
    SELECT 
        theme_name
        , SUM(low_signal + gc_signal + high_signal + dc_signal) as "종목수"
        , SUM(low_signal) as "MACD음수맥스"
        , SUM(gc_signal) as "골든크로스"
        , SUM(high_signal) as "MACD양수맥스"
        , SUM(dc_signal) as "데드크로스"
        , ROUND(SUM(weighted_score_contrib)::numeric, 4) as rotation_score
        , MAX(date) as date
    FROM weighted_signals
    GROUP BY theme_name
    HAVING SUM(low_signal + gc_signal + high_signal + dc_signal) >= 3 -- 신호 발생 종목수 기준 필터링
)
-- 8. 최종 출력 (순위 추가 및 국면 진단)
SELECT 
    to_char(date, 'YYYY-MM-DD') as "날짜"
    , ROW_NUMBER() OVER(ORDER BY rotation_score DESC) as "순위"
    , theme_name as "업종명"
    , "종목수"
/*
    , "MACD음수맥스"
    , "골든크로스"
    , "MACD양수맥스"
    , "데드크로스"
    , rotation_score as "로테이션스코어"
    , CASE 
        WHEN rotation_score >= 5 THEN '강력 회복'
        WHEN rotation_score >= 1 THEN '회복 진행'
        WHEN rotation_score <= -5 THEN '강한 하락'
        WHEN rotation_score <= -1 THEN '하락 전환'
        ELSE '중립/혼조'
      END as "국면진단"
*/      
FROM final_aggregation
ORDER BY 
    rotation_score DESC
    , theme_name ASC;
