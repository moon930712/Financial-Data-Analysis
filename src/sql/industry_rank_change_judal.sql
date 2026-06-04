WITH histo_base AS (
    -- 1. MACD 히스토그램 데이터 산출 (순위 변동 분석을 위해 기간 확보)
    SELECT 
        m.date, m.stock_code, m.stock_name, (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
    WHERE date >= '2026-03-20' AND date <= '2026-04-03'
),
phase_classification AS (
    -- 2. 4대 국면 분류
    SELECT 
        date, stock_code, stock_name
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1 -- 회복기
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 -- 하락기
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 -- 상승기
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 -- 둔화기
            ELSE 4
          END as phase
    FROM histo_base
    WHERE date >= '2026-03-29' -- 전일 비교를 위해 하루 전부터 데이터 포함
),
theme_aggregation AS (
    -- 3. 주달(Judal) 테마별 일자별 집계
    SELECT 
        nt.theme_name, p.date, COUNT(*) as total_cnt
        , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
    FROM industry.theme_name_list nt
    JOIN phase_classification p ON nt.stock_code = p.stock_code
    WHERE nt.theme_name != '테마없음' 
      AND nt.theme_name NOT LIKE '%스팩%'
      AND nt.theme_name NOT LIKE '%ETF%'
      AND nt.theme_name NOT LIKE '%ETN%'
    GROUP BY nt.theme_name, p.date
    HAVING COUNT(*) >= 3
),
daily_ranking AS (
    -- 4. 일자별 테마 순위 매기기 (가중치 점수 기준)
    SELECT 
        date, theme_name, total_cnt, phase1_cnt, phase3_cnt
        , ((phase1_cnt::numeric * 1.5 + phase3_cnt::numeric) / total_cnt) as weighted_score
        , ROW_NUMBER() OVER(PARTITION BY date ORDER BY ((phase1_cnt::numeric * 1.5 + phase3_cnt::numeric) / total_cnt) DESC, total_cnt DESC) as rank
    FROM theme_aggregation
),
rank_change_calc AS (
    -- 5. 전일 대비 순위 변동폭(Momentum) 계산
    SELECT 
        *
        , LAG(rank, 1) OVER(PARTITION BY theme_name ORDER BY date) as prev_rank
        , (LAG(rank, 1) OVER(PARTITION BY theme_name ORDER BY date) - rank) as momentum
    FROM daily_ranking
),
momentum_ranking AS (
    -- 6. ★ 전체 테마 중 변동폭이 큰 순서대로 '변동폭별 순위' 부여 (일자별 파티션)
    SELECT
        *
        , ROW_NUMBER() OVER(PARTITION BY date ORDER BY momentum DESC, rank ASC) as change_rank
    FROM rank_change_calc
    WHERE prev_rank IS NOT NULL
)
-- 7. 최종 출력 (요청하신 5개 컬럼 구성)
SELECT 
    to_char(date, 'YYYY-MM-DD') as "날짜"
    , theme_name as "테마명"
    , rank as "현재순위"
    , prev_rank as "전일순위"
    , change_rank as "변동폭별 순위"
FROM momentum_ranking
WHERE date >= '2026-03-30'
  AND (theme_name LIKE '%로봇%' OR theme_name LIKE '%조선%' OR theme_name LIKE '%해양플랜트%')
ORDER BY 
    "날짜" DESC
    , "변동폭별 순위" ASC;
