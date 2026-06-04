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
      -- ★ 최신 일자만 보는 것에서 특정 기간(3월 30일 ~ 4월 3일)을 보도록 변경
      AND date >= '2026-03-30' AND date <= '2026-04-03'
)
, theme_aggregation AS (
    -- 3. ★ 주달(Judal) 테마 테이블 기준으로 집계 (일자별 그룹핑)
    SELECT 
        nt.theme_name
        , p.date
        , COUNT(*) as total_cnt
        , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
        , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt
        , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt
        , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
    FROM industry.theme_name_list nt -- 네이버 테마 대신 주달 테이블 사용
    JOIN phase_classification p ON nt.stock_code = p.stock_code
    WHERE 1=1
      AND nt.theme_name != '테마없음'     -- 주달의 '테마없음' 제외
      AND nt.theme_name NOT LIKE '%스팩%' -- 스팩 관련 제외
      AND nt.theme_name NOT LIKE '%ETF%'  -- ETF 제외
      AND nt.theme_name NOT LIKE '%ETN%'  -- ETN 제외
    GROUP BY nt.theme_name, p.date
    HAVING COUNT(*) >= 3 -- 3종목 이상 의미 있는 테마만 분석
)
, ratio_calculation AS (
    -- 4. 가중치 점수 및 국면별 비율(%) 계산
    SELECT 
        *
        -- ★ 가중치 점수: (회복기 * 1.5 + 상승기) / 전체종목수
        , ROUND(((phase1_cnt::numeric * 1.5 + phase3_cnt::numeric) / total_cnt), 4) as weighted_score
        , ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) as phase1_ratio
        , ROUND((phase2_cnt::numeric / total_cnt) * 100, 2) as phase2_ratio
        , ROUND((phase3_cnt::numeric / total_cnt) * 100, 2) as phase3_ratio
        , ROUND((phase4_cnt::numeric / total_cnt) * 100, 2) as phase4_ratio
    FROM theme_aggregation
)
, final_ranking AS (
    -- 5. 가중치 점수(weighted_score) 기준으로 일자별 글로벌 순위 산정
    SELECT 
        to_char(date, 'YYYY-MM-DD') as date_str
        , ROW_NUMBER() OVER(PARTITION BY date ORDER BY weighted_score DESC, phase1_ratio DESC, total_cnt DESC) as global_rank
        , COUNT(*) OVER(PARTITION BY date) as total_themes_cnt
        , theme_name
        , total_cnt
        , phase1_cnt
        , phase1_ratio
        , phase2_ratio
        , phase3_ratio
        , phase4_ratio
        , weighted_score
    FROM ratio_calculation
)
-- 6. 최종 출력 (로봇 테마 필터링)
SELECT 
    date_str as "날짜"
    , global_rank::varchar || ' / ' || total_themes_cnt::varchar as "순위(/전체)"
    , theme_name as "업종명(주달)"
    , weighted_score as "가중치점수"
    , total_cnt as "종목수"
    , phase1_cnt as "회복기종목수"
    , phase1_ratio as "회복기비율(%)"
    , phase3_ratio as "상승기비율(%)"
    , phase2_ratio as "하락기비율(%)"
    , phase4_ratio as "둔화기비율(%)"
FROM final_ranking
WHERE theme_name LIKE '%로봇%' OR theme_name LIKE '%조선%' OR theme_name LIKE '%해양플랜트%' -- ★ 로봇 또는 조선 테마 검색
ORDER BY 
    date_str DESC
    , global_rank ASC
    , theme_name ASC;
