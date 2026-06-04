-- 생애주기 4국면(Phases) 비율 기반 업종 순환매 마스터 분석
-- 작성일: 2026-04-16
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
theme_aggregation AS (
    -- 3. 테마별 전체 종목수 및 국면별 종목수 집계 (SPAC 제외)
    SELECT 
        nt.theme_name
        , COUNT(*) as total_cnt
        , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
        , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt
        , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt
        , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
        , MAX(p.date) as date
    FROM company.naver_theme nt
    JOIN phase_classification p ON nt.stock_code = p.stock_code
    WHERE 1=1
      AND nt.theme_name != '기업인수목적회사(SPAC)'
    GROUP BY nt.theme_name
    HAVING COUNT(*) >= 3 -- 통계적 유의성을 위해 3종목 이상 테마만 포함
),
ratio_calculation AS (
    -- 4. 국면별 비율(%) 계산 및 정렬용 우선순위 부여
    SELECT 
        *
        , ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) as phase1_ratio
        , ROUND((phase2_cnt::numeric / total_cnt) * 100, 2) as phase2_ratio
        , ROUND((phase3_cnt::numeric / total_cnt) * 100, 2) as phase3_ratio
        , ROUND((phase4_cnt::numeric / total_cnt) * 100, 2) as phase4_ratio
    FROM theme_aggregation
)
final_ranking AS (
    -- 5. 전체 대상 글로벌 순위 및 전체 업종 개수(분모) 사전 계산
    SELECT 
        to_char(date, 'YYYY-MM-DD') as date_str
        , ROW_NUMBER() OVER(ORDER BY phase1_ratio DESC, phase2_ratio DESC, phase3_ratio DESC, total_cnt DESC) as global_rank
        , COUNT(*) OVER() as total_themes_cnt
        , theme_name
        , total_cnt
        , phase1_cnt
        , phase1_ratio
        , phase2_ratio
        , phase3_ratio
        , phase4_ratio
    FROM ratio_calculation
)
-- 6. 최종 출력
SELECT 
    date_str as "날짜"
    , global_rank::varchar || ' / ' || total_themes_cnt::varchar as "전체순위"
    , theme_name as "업종명"
    , total_cnt as "업종의 전체종목수"
    , phase1_cnt as "회복종목수"
    , phase1_ratio as "회복기비율(%)"
    , phase2_ratio as "하락기비율(%)"
    , phase3_ratio as "상승기비율(%)"
    , phase4_ratio as "둔화기비율(%)"
FROM final_ranking
-- 특정 테마(예: 로봇)만 필터링하여 전체 대비 순위를 보고 싶을 경우 아래 주석을 해제하세요.
-- WHERE theme_name LIKE '%로봇%'
ORDER BY 
    global_rank ASC
    , theme_name ASC;
