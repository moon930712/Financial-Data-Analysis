-- 회복기(Phase 1) 지속 기간 및 0선 돌파까지의 유예 기간 분석 (수정본)
WITH histo_base AS (
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
phase_label AS (
    SELECT 
        *
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1 -- 제1국면 (회복기)
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 2 -- 제2국면 (상승기)
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 3 -- 제3국면 (하락기)
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 -- 제4국면 (둔화기)
            ELSE 0
          END as phase
        , CASE WHEN histogram >= 0 THEN 1 ELSE -1 END as side
    FROM histo_base
),
side_with_lag AS (
    -- LAG를 별도 추출하여 중첩 방지
    SELECT 
        *
        , LAG(side, 1) OVER(PARTITION BY stock_code ORDER BY date) as prev_side
    FROM phase_label
),
islands AS (
    -- 0선 기준 아일랜드 구분
    SELECT 
        *
        , SUM(CASE WHEN side = prev_side THEN 0 ELSE 1 END) 
          OVER(PARTITION BY stock_code ORDER BY date) as island_id
    FROM side_with_lag
),
recovery_sub_islands AS (
    -- 음수 아일랜드 내에서 '회복기(Phase 1)' 연속성 그룹화
    SELECT 
        *
        , SUM(CASE WHEN phase = 1 THEN 0 ELSE 1 END) OVER(PARTITION BY stock_code, island_id ORDER BY date) as recovery_group
    FROM islands
    WHERE side = -1
),
recovery_durations AS (
    -- 회복기 지속 일수 산출
    SELECT 
        stock_code
        , stock_name
        , island_id
        , COUNT(*) as recovery_days
        , MAX(date) as end_date
    FROM recovery_sub_islands
    WHERE phase = 1
    GROUP BY stock_code, stock_name, island_id, recovery_group
),
stock_sector_info AS (
    SELECT DISTINCT stock_code, wics_name2 as mid_sector_name
    FROM visual.vsl_krx_stocks_cap
)
SELECT 
    si.mid_sector_name as "중분류"
    , rd.stock_name as "종목명"
    , rd.recovery_days as "회복기지속일수"
    , to_char(rd.end_date, 'YYYY-MM-DD') as "회복종료일"
FROM recovery_durations rd
JOIN stock_sector_info si ON rd.stock_code = si.stock_code
ORDER BY rd.end_date DESC, rd.recovery_days DESC;
