-- 생애주기 4국면(Phases) 비율 기반 섹터 순환매 마스터 분석
-- 작성일: 2026-04-17
WITH histo_base AS (
    -- 1. MACD 히스토그램 기본 및 Lag 데이터 산출
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
phase_classification AS (
    -- 2. 모든 종목을 4대 국면으로 100% 분류
    SELECT 
        date
        , stock_code
        , stock_name
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1 -- 제1국면 (회복기)
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 -- 제2국면 (하락기)
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 -- 제3국면 (상승기)
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 -- 제4국면 (둔화기)
            ELSE 4
          END as phase
    FROM histo_base
    WHERE 1=1
      AND date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02)
),
stock_sector_info AS (
    -- 3. 종목 WICS 섹터 정보 결합
    SELECT DISTINCT
        stock_code,
        wics_name3 as sector_name
    FROM visual.vsl_krx_stocks_cap
    where 1=1
      and wics_name3 != '미분류'
),
sector_aggregation AS (
    -- 4. 섹터별 전체 종목수 및 국면별 종목수 집계
    SELECT 
        si.sector_name
        , COUNT(*) as total_cnt
        , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
        , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt
        , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt
        , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
        , MAX(p.date) as date
    FROM stock_sector_info si
    JOIN phase_classification p ON si.stock_code = p.stock_code
    WHERE 1=1
      AND si.sector_name IS NOT NULL
      AND TRIM(si.sector_name) != ''
    GROUP BY si.sector_name
    HAVING COUNT(*) >= 3 -- 통계적 유의성을 위해 3종목 이상 섹터만 포함
),
ratio_calculation AS (
    -- 5. 국면별 비율(%) 계산 및 정렬용 우선순위 부여
    SELECT 
        *
        , ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) as phase1_ratio
        , ROUND((phase2_cnt::numeric / total_cnt) * 100, 2) as phase2_ratio
        , ROUND((phase3_cnt::numeric / total_cnt) * 100, 2) as phase3_ratio
        , ROUND((phase4_cnt::numeric / total_cnt) * 100, 2) as phase4_ratio
    FROM sector_aggregation
)
-- 6. 최종 출력 (정렬: 1국면(회복기) 비율 DESC -> 2국면(하락기) 비율 DESC -> 3국면(상승기) 비율 DESC -> 전체종목수 DESC)
SELECT 
    to_char(date, 'YYYY-MM-DD') as "날짜"
    , ROW_NUMBER() OVER(ORDER BY phase1_ratio DESC, phase2_ratio DESC, phase3_ratio DESC, total_cnt DESC) as "순위"
    , sector_name as "업종명"
    , total_cnt as "업종의 전체종목수"
--    , phase1_cnt as "회복종목수"
    , phase1_ratio as "회복기비율(%)"
    , phase2_ratio as "하락기비율(%)"
    , phase3_ratio as "상승기비율(%)"
    , phase4_ratio as "둔화기비율(%)"
FROM ratio_calculation
ORDER BY 
    phase1_ratio DESC
    , phase2_ratio DESC
    , phase3_ratio DESC
    , total_cnt DESC
    , sector_name ASC;
