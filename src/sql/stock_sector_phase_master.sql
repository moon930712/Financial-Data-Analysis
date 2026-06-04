-- 생애주기 4국면(Phases) 섹터별 종목 상세 리스트 (현황판 연동용)
-- 작성일: 2026-04-17 (최종 수정: 2026-04-23 회복기 세분화 적용)
WITH histo_base AS (
    -- 1. MACD 히스토그램 기본 및 Lag 데이터 산출 (이력 포함)
    SELECT 
        m.date
        , m.stock_code
        , m.stock_name
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        , p.close AS close_price
    FROM visual.vsl_anly_stocks_price_subindex02 m
    LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p 
      ON m.stock_code = p.stock_code AND m.date = p.date
    WHERE m.date > (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02) - INTERVAL '20 days'
),
phase_raw AS (
    -- 2. 기본 국면 분류
    SELECT 
        *
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
    -- 3. 연속 회복기 지속 일수(Tenure) 계산
    SELECT 
        stock_code
        , COUNT(*) as recovery_days
    FROM (
        SELECT 
            stock_code, phase, date,
            SUM(CASE WHEN phase = 1 THEN 0 ELSE 1 END) OVER(PARTITION BY stock_code ORDER BY date DESC) as grp
        FROM phase_raw
    ) t
    WHERE phase = 1 AND grp = 0
    GROUP BY stock_code
),
phase_classification AS (
    -- 4. 최신일자 기준 국면 확정 및 회복기 세분화
    SELECT 
        p.date
        , p.stock_code
        , p.stock_name
        , (p.histogram / NULLIF(p.close_price, 0)) * 100 AS normalized_histogram
        , p.phase as phase_rank
        , CASE 
            WHEN p.phase = 1 AND COALESCE(rt.recovery_days, 0) <= 2 THEN '회복기(진입)'
            WHEN p.phase = 1 AND COALESCE(rt.recovery_days, 0) > 2 THEN '회복기(지속)'
            WHEN p.phase = 2 THEN '상승기'
            WHEN p.phase = 3 THEN '하락기'
            WHEN p.phase = 4 THEN '둔화기'
            ELSE '둔화기'
          END as phase_name
    FROM phase_raw p
    LEFT JOIN recovery_tenure rt ON p.stock_code = rt.stock_code
    WHERE p.date = (SELECT MAX(date) FROM phase_raw)
),
stock_sector_info AS (
    -- 5. 종목 WICS 섹터 정보 및 시총 결합
    SELECT 
        stock_code,
        wics_name3 AS sector_name,
        cap as market_cap
    FROM visual.vsl_krx_stocks_cap
    WHERE 1=1
      AND date = (SELECT MAX(date) FROM visual.vsl_krx_stocks_cap)
      AND wics_name3 != '미분류'
),
sector_stocks AS (
    -- 6. 섹터명 및 시총 정보 병합
    SELECT 
        p.date
        , si.sector_name
        , p.stock_name
        , p.phase_name
        , p.phase_rank
        , p.normalized_histogram
        , si.market_cap
    FROM phase_classification p
    JOIN stock_sector_info si ON p.stock_code = si.stock_code
    WHERE 1=1
      AND si.sector_name IS NOT NULL
      AND TRIM(si.sector_name) != ''
)
-- 7. 최종 출력
SELECT 
    to_char(date, 'YYYY-MM-DD') as "날짜"
    , sector_name as "업종명"
    , stock_name as "종목명"
    , phase_name as "현재국면"
    , ROW_NUMBER() OVER(PARTITION BY sector_name ORDER BY market_cap DESC) as "업종내시총순위"
FROM sector_stocks
WHERE 1=1
  -- 🔥 그라파나 All 처리 및 변수 연동
  AND ( 'All' IN (${wics_name:sqlstring}) OR sector_name IN (${wics_name:sqlstring}) )
ORDER BY 
    phase_rank ASC    -- 1(회복) -> 2(상승) -> 3(하락) -> 4(둔화)
    , CASE WHEN phase_rank IN (1, 3) THEN ABS(normalized_histogram) ELSE NULL END DESC 
    , CASE WHEN phase_rank IN (2, 4) THEN ABS(normalized_histogram) ELSE NULL END ASC  
    , market_cap DESC; -- 같은 국면 내에선 시총순 정렬 추가
