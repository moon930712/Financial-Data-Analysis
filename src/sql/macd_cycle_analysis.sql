-- MACD 히스토그램 0선 교차 주기(지속 기간) 분석 쿼리
WITH histo_raw AS (
    -- 1. MACD 히스토그램 및 기본 정보 추출
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , CASE WHEN (m.macd - m.signal) >= 0 THEN 1 ELSE -1 END as side
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
histo_with_lag AS (
    -- 2. 이전 행의 side와 비교하여 변경 시점 포착
    SELECT 
        *
        , LAG(side, 1) OVER(PARTITION BY stock_code ORDER BY date) as prev_side
    FROM histo_raw
),
histo_islands AS (
    -- 3. Gaps and Islands: side가 바뀔 때마다 cumulative sum을 증가시켜 고유 그룹 ID 생성
    SELECT 
        *
        , SUM(CASE WHEN side = prev_side THEN 0 ELSE 1 END) OVER(PARTITION BY stock_code ORDER BY date) as island_id
    FROM histo_with_lag
),
island_durations AS (
    -- 4. 각 아일랜드(구간)별 시작일, 종료일, 지속 기간 계산
    SELECT 
        stock_code
        , stock_name
        , island_id
        , side
        , MIN(date) as start_date
        , MAX(date) as end_date
        , COUNT(*) as duration_days
    FROM histo_islands
    GROUP BY stock_code, stock_name, island_id, side
),
stock_sector_info AS (
    -- 5. WICS 중분류/소분류 정보 결합
    SELECT DISTINCT
        stock_code,
        wics_name2 as mid_sector_name,
        wics_name3 as sector_name
    FROM visual.vsl_krx_stocks_cap
    WHERE wics_name3 != '미분류'
)
-- 6. 최종 결과: 업종 정보와 결합된 구간 정보
SELECT 
    si.mid_sector_name as "중분류"
    , si.sector_name as "소분류"
    , id.stock_name as "종목명"
    , id.stock_code as "종목코드"
    , CASE WHEN id.side = 1 THEN '상승구간(0선위)' ELSE '하락구간(0선밑)' END as "구간구분"
    , to_char(id.start_date, 'YYYY-MM-DD') as "시작일"
    , to_char(id.end_date, 'YYYY-MM-DD') as "종료일"
    , id.duration_days as "지속일수"
FROM island_durations id
JOIN stock_sector_info si ON id.stock_code = si.stock_code
WHERE id.duration_days > 1 -- 하루짜리 노이즈 제거 (선택 사항)
ORDER BY id.start_date DESC, id.duration_days DESC;
