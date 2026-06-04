WITH raw_data AS (
    -- 1. LAG 함수 NULL 방지를 위한 여유 기간 데이터 추출
    SELECT 
        date, stock_code, stock_name, (macd - signal) AS histogram
    FROM visual.vsl_anly_stocks_price_subindex02
    WHERE date >= '2026-03-15' AND date <= '2026-04-20' -- ★ 기간 연장
)
,histo_base AS (
    -- 2. MACD 히스토그램 및 Lag 산출
    SELECT 
        date, stock_code, stock_name, histogram
        , LAG(histogram, 1) OVER(PARTITION BY stock_code ORDER BY date) AS lag_histogram
    FROM raw_data
)
,phase_raw AS (
    -- 3. 4대 국면 분류 (텍스트 변환)
    SELECT 
        date, stock_code, stock_name
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN '회복기'
            WHEN histogram < 0 AND histogram <= lag_histogram THEN '하락기'
            WHEN histogram >= 0 AND histogram > lag_histogram THEN '상승기'
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN '둔화기'
            ELSE '둔화기'
        END AS phase_name
    FROM histo_base
    WHERE date BETWEEN '2026-03-30' AND '2026-04-20' -- ★ 기간 연장
)
,target_stocks AS (
    -- 4. ★ 주달(Judal) 테마 테이블에서 로봇/조선/해양플랜트 관련 종목 필터링
    SELECT DISTINCT
        stock_code
        ,theme_name
    FROM 
        industry.theme_name_list
    WHERE 
        (theme_name LIKE '%로봇%' OR theme_name LIKE '%조선%' OR theme_name LIKE '%해양플랜트%')
        AND theme_name != '테마없음'
)
,stock_info AS (
    -- 5. 시가총액 정보 결합 (KOSPI/KOSDAQ 정렬용)
    SELECT shortcode, marketcap FROM company.kis_kospi_info
    UNION ALL
    SELECT shortcode, previousdaymarketcap as marketcap FROM company.kis_kosdaq_info
)
-- 6. 날짜별 피벗 출력 (4월 20일까지 확장)
SELECT 
    p.stock_name AS "종목명"
    ,t.theme_name AS "주달테마"
    -- 3월
    ,MAX(CASE WHEN p.date = '2026-03-30' THEN p.phase_name END) AS "3/30"
    ,MAX(CASE WHEN p.date = '2026-03-31' THEN p.phase_name END) AS "3/31"
    -- 4월 1주차
    ,MAX(CASE WHEN p.date = '2026-04-01' THEN p.phase_name END) AS "4/1"
    ,MAX(CASE WHEN p.date = '2026-04-02' THEN p.phase_name END) AS "4/2"
    ,MAX(CASE WHEN p.date = '2026-04-03' THEN p.phase_name END) AS "4/3"
    -- 4월 2주차
    ,MAX(CASE WHEN p.date = '2026-04-06' THEN p.phase_name END) AS "4/6"
    ,MAX(CASE WHEN p.date = '2026-04-07' THEN p.phase_name END) AS "4/7"
    ,MAX(CASE WHEN p.date = '2026-04-08' THEN p.phase_name END) AS "4/8"
    ,MAX(CASE WHEN p.date = '2026-04-09' THEN p.phase_name END) AS "4/9"
    ,MAX(CASE WHEN p.date = '2026-04-10' THEN p.phase_name END) AS "4/10"
    -- 4월 3주차
    ,MAX(CASE WHEN p.date = '2026-04-13' THEN p.phase_name END) AS "4/13"
    ,MAX(CASE WHEN p.date = '2026-04-14' THEN p.phase_name END) AS "4/14"
    ,MAX(CASE WHEN p.date = '2026-04-15' THEN p.phase_name END) AS "4/15"
    ,MAX(CASE WHEN p.date = '2026-04-16' THEN p.phase_name END) AS "4/16"
    ,MAX(CASE WHEN p.date = '2026-04-17' THEN p.phase_name END) AS "4/17"
    -- 4월 4주차
    ,MAX(CASE WHEN p.date = '2026-04-20' THEN p.phase_name END) AS "4/20"
FROM 
    phase_raw p
JOIN 
    target_stocks t ON p.stock_code = t.stock_code
LEFT JOIN 
    stock_info s ON p.stock_code = s.shortcode
GROUP BY 
    p.stock_code
    ,p.stock_name
    ,t.theme_name
    ,s.marketcap
ORDER BY 
    t.theme_name ASC
    ,s.marketcap DESC NULLS LAST
    ,p.stock_name ASC;
