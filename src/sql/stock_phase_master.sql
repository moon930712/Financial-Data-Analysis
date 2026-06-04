-- 생애주기 4국면(Phases) 고도화: 회복기 세분화 및 중분류-소분류 마스터 점수 기반 섹터 순환매 분석
WITH histo_base AS (
    -- 1. MACD 히스토그램 및 기본 데이터 (이력 포함)
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
    WHERE m.date > (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02) - INTERVAL '20 days'
),
phase_classification AS (
    -- 2. 국면 분류 및 회복기 지속 일수(Tenure) 계산 준비
    SELECT 
        date
        , stock_code
        , stock_name
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1 -- 제1국면 (회복기)
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 2 -- 제2국면 (상승기)
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 3 -- 제3국면 (하락기)
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 -- 제4국면 (둔화기)
            ELSE 4
          END as phase
    FROM histo_base
),
recovery_tenure AS (
    -- 3. 현재 날짜 기준 연속 회복기 지속 일수 산출
    SELECT 
        stock_code
        , COUNT(*) as recovery_days
    FROM (
        SELECT 
            stock_code, phase, date,
            SUM(CASE WHEN phase = 1 THEN 0 ELSE 1 END) OVER(PARTITION BY stock_code ORDER BY date DESC) as grp
        FROM phase_classification
    ) t
    WHERE phase = 1 AND grp = 0
    GROUP BY stock_code
),
final_phase_classification AS (
    -- 4. 최신 날짜 기준 회복기 세분화 (1.1: 초기, 1.2: 성숙)
    SELECT 
        p.date
        , p.stock_code
        , p.stock_name
        , CASE 
            WHEN p.phase = 1 AND COALESCE(rt.recovery_days, 0) <= 2 THEN 1.1 -- 초기 회복기 (1~2일)
            WHEN p.phase = 1 AND COALESCE(rt.recovery_days, 0) > 2 THEN 1.2 -- 성숙 회복기 (3일 이상)
            ELSE p.phase::numeric
          END as refined_phase
    FROM phase_classification p
    LEFT JOIN recovery_tenure rt ON p.stock_code = rt.stock_code
    WHERE p.date = (SELECT MAX(date) FROM phase_classification)
),
stock_sector_info AS (
    SELECT DISTINCT
        stock_code,
        wics_name2 as mid_sector_name,
        wics_name3 as sector_name
    FROM visual.vsl_krx_stocks_cap
    WHERE wics_name3 != '미분류'
),
mid_sector_stats AS (
    -- 5. 중분류별 회복기 비중 산출
    SELECT 
        si.mid_sector_name
        , ROUND((SUM(CASE WHEN p.refined_phase IN (1.1, 1.2) THEN 1 ELSE 0 END)::numeric / COUNT(*)) * 100, 2) as mid_phase1_ratio
    FROM stock_sector_info si
    JOIN final_phase_classification p ON si.stock_code = p.stock_code
    GROUP BY si.mid_sector_name
),
sector_aggregation AS (
    -- 6. 소분류별 집계 및 중분류 데이터 결합
    SELECT 
        si.mid_sector_name
        , si.sector_name
        , COUNT(*) as total_cnt
        , SUM(CASE WHEN p.refined_phase = 1.1 THEN 1 ELSE 0 END) as phase1_1_cnt
        , SUM(CASE WHEN p.refined_phase = 1.2 THEN 1 ELSE 0 END) as phase1_2_cnt
        , SUM(CASE WHEN p.refined_phase = 2 THEN 1 ELSE 0 END) as phase2_cnt
        , ms.mid_phase1_ratio
        , MAX(p.date) as date
    FROM stock_sector_info si
    JOIN final_phase_classification p ON si.stock_code = p.stock_code
    JOIN mid_sector_stats ms ON si.mid_sector_name = ms.mid_sector_name
    WHERE si.sector_name IS NOT NULL
    GROUP BY si.mid_sector_name, si.sector_name, ms.mid_phase1_ratio
    HAVING COUNT(*) >= 3 
),
ratio_calculation AS (
    -- 7. 마스터 스코어 산출 (소분류 70% + 중분류 30%)
    -- 회복기 1.1(초기)에 1.2 가중치 부여, 회복기 1.2에 1.0 가중치 부여
    SELECT 
        *
        , ROUND(((phase1_1_cnt::numeric * 1.5 + phase1_2_cnt) / total_cnt) * 100, 2) as sub_phase1_score
        , ROUND((((phase1_1_cnt + phase1_2_cnt)::numeric / total_cnt) * 100 * 0.3) + (mid_phase1_ratio * 0.7), 2) as master_score
        , ROUND(((phase1_1_cnt + phase1_2_cnt)::numeric / total_cnt) * 100, 2) as phase1_total_ratio
    FROM sector_aggregation
)
-- 8. 최종 출력
SELECT 
    to_char(date, 'YYYY-MM-DD') as "날짜"
    , ROW_NUMBER() OVER(ORDER BY master_score DESC, phase1_total_ratio DESC, total_cnt DESC) as "순위"
    , mid_sector_name as "중분류명"
    , sector_name as "소분류명"
--    , master_score as "마스터점수"
    , phase1_total_ratio as "회복기비율(%)"
--    , mid_phase1_ratio as "중분류_회복기비율(%)"
--    , phase1_1_cnt as "회복기1(초기)종목수"
--    , phase1_2_cnt as "회복기2(성숙)종목수"
    , total_cnt as "업종내종목수"
FROM ratio_calculation
WHERE 1=1
--  AND ( 'All' IN (${wics_name2:sqlstring}) OR mid_sector_name IN (${wics_name2:sqlstring}) )
ORDER BY 
    master_score DESC
    , phase1_total_ratio DESC
    , total_cnt DESC;
