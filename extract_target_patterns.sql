-- V3 필터(RSI, 거래대금 등)를 모두 만족하는 "진짜 알짜 종목"들을
-- 1달(한 달) 기간 동안 발굴된 내역 전부를 최상단에 먼저 노출하도록 정렬하는 쿼리

WITH target_date AS (
    SELECT 
        CASE 
            WHEN ${date:sqlstring} = '' OR ${date:sqlstring} = 'All' OR ${date:sqlstring} IS NULL 
            THEN (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02) 
            ELSE CAST(${date:sqlstring} AS DATE) 
        END AS dt
)
, all_valid_dates AS (
    -- 최근 1달 데이터 추출을 위해, 과거 이동평균(20일)과 패턴 계산(3일)을 고려하여 넉넉히 최근 60일치 영업일 확보
    SELECT DISTINCT date 
    FROM visual.vsl_anly_stocks_price_subindex01 
    WHERE date <= (SELECT dt FROM target_date)
      AND date >= (SELECT dt FROM target_date) - INTERVAL '60 days'
)
-- [1. 테마 랭킹 산출을 위한 기초 국면 작업]
, theme_histo_base AS (
    SELECT 
        m.date
        , m.stock_code
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
    WHERE m.date IN (SELECT date FROM all_valid_dates)
)
, theme_phase_classification AS (
    SELECT 
        date
        , stock_code
        , CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1 
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 2 
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 3 
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4 
            ELSE 4 
          END as phase
    FROM theme_histo_base
)
, theme_aggregation AS (
    SELECT 
        nt.theme_name
        , p.date
        , COUNT(*) as total_cnt
        , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) as phase1_cnt
        , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) as phase2_cnt
        , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) as phase3_cnt
        , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) as phase4_cnt
        , COALESCE(SUM(v1.trade_value), 0) / COUNT(*) AS avg_trade_value
    FROM industry.theme_name_list nt
    INNER JOIN theme_phase_classification p ON nt.stock_code = p.stock_code
    LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
    WHERE v1.close > 1000 
    GROUP BY nt.theme_name, p.date
    HAVING COUNT(*) >= 5
)
, trade_rank_calc AS (
    SELECT *, ROW_NUMBER() OVER(PARTITION BY date ORDER BY avg_trade_value DESC NULLS LAST) AS trade_value_rank
    FROM theme_aggregation
)
, final_ranking AS (
    SELECT date, theme_name
        , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
            ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
            ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
            total_cnt DESC
          ) AS global_rank
    FROM trade_rank_calc
    WHERE trade_value_rank <= 150
)
-- [2. 타겟 테마 패턴 산출 (매일매일의 3일 롤링 패턴 평가)]
, date_theme_ranks AS (
    SELECT 
        date
        , theme_name
        , global_rank as rank_d0
        , LAG(global_rank, 1) OVER(PARTITION BY theme_name ORDER BY date) as rank_d1
        , LAG(global_rank, 2) OVER(PARTITION BY theme_name ORDER BY date) as rank_d2
    FROM final_ranking
)
, theme_grades AS (
    SELECT 
        date
        , theme_name
        , rank_d0
        , CASE WHEN rank_d2 <= 25 THEN '1등급' WHEN rank_d2 <= 50 THEN '2등급' WHEN rank_d2 <= 75 THEN '3등급' WHEN rank_d2 <= 100 THEN '4등급' WHEN rank_d2 <= 125 THEN '5등급' ELSE '6등급' END
          || ' -> ' ||
          CASE WHEN rank_d1 <= 25 THEN '1등급' WHEN rank_d1 <= 50 THEN '2등급' WHEN rank_d1 <= 75 THEN '3등급' WHEN rank_d1 <= 100 THEN '4등급' WHEN rank_d1 <= 125 THEN '5등급' ELSE '6등급' END
          || ' -> ' ||
          CASE WHEN rank_d0 <= 25 THEN '1등급' WHEN rank_d0 <= 50 THEN '2등급' WHEN rank_d0 <= 75 THEN '3등급' WHEN rank_d0 <= 100 THEN '4등급' WHEN rank_d0 <= 125 THEN '5등급' ELSE '6등급' END
          AS pattern
    FROM date_theme_ranks
    WHERE rank_d0 <= 20
      -- 추출 기간을 1달로 한정 (과거 데이터는 지표 계산용으로만 씀)
      AND date >= (SELECT dt FROM target_date) - INTERVAL '2 month'
)
, target_themes AS (
    SELECT date, theme_name, pattern
    FROM theme_grades
    WHERE pattern IN (
        '6등급 -> 4등급 -> 1등급',
        '4등급 -> 3등급 -> 1등급',
        '3등급 -> 2등급 -> 1등급'
    )
)
-- [3. 종목별 V3 지표 산출]
, stock_indicators AS (
    SELECT 
        v1.date
        , v1.stock_code
        , v2.rsi
        , v1.ma20
        , v1.open
        , v1.close
        , v1.trade_value
        , (v1.close / NULLIF(v1.ma20, 0)) * 100 AS disparity_20
        , (v1.trade_value / NULLIF(AVG(v1.trade_value) OVER(PARTITION BY v1.stock_code ORDER BY v1.date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING), 0)) AS volume_spike
    FROM visual.vsl_anly_stocks_price_subindex01 v1
    JOIN visual.vsl_anly_stocks_price_subindex02 v2 ON v1.stock_code = v2.stock_code AND v1.date = v2.date
    WHERE v1.date IN (SELECT date FROM all_valid_dates)
)
-- [4. 최근 3일 스마트머니(외인+기관 순매수) 롤링 합산]
, daily_sm AS (
    SELECT 
        date
        , stock_code
        , SUM(CASE WHEN investor IN ('기관합계', '외국인') THEN net_trade_vol ELSE 0 END) as daily_sm_flow
    FROM visual.vsl_krx_stocks_investor_shares_trading_info
    WHERE date IN (SELECT date FROM all_valid_dates)
    GROUP BY date, stock_code
)
, smart_money AS (
    SELECT 
        date
        , stock_code
        , SUM(daily_sm_flow) OVER(PARTITION BY stock_code ORDER BY date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as sm_flow
    FROM daily_sm
)
-- [5. 최종 결과 도출 (최근 1달 치)]
SELECT 
    TO_CHAR(tt.date, 'YYYY-MM-DD') AS "날짜"
    , tt.theme_name AS "테마명"
    , tt.pattern AS "패턴"
    , nl.stock_name AS "종목명"
    , CASE tpc.phase 
        WHEN 1 THEN '회복기(1국면)' 
        WHEN 3 THEN '상승기(3국면)' 
      END AS "종목국면"
    , '추천종목' AS "조건만족"
    , CASE WHEN ts.close >= ts.open * 1.10 THEN 'O' ELSE '' END AS "10% 이상 급등"
FROM target_themes tt
JOIN industry.theme_name_list nl ON tt.theme_name = nl.theme_name
JOIN theme_phase_classification tpc 
  ON nl.stock_code = tpc.stock_code 
 AND tpc.date = tt.date
JOIN stock_indicators ts 
  ON nl.stock_code = ts.stock_code 
 AND ts.date = tt.date
JOIN smart_money sm 
  ON nl.stock_code = sm.stock_code 
 AND sm.date = tt.date
WHERE tpc.phase IN (1, 3)
  -- 오직 V3 필터를 만족한 '알짜 종목'들만 노출
  AND ts.volume_spike >= 1.8
  AND COALESCE(sm.sm_flow, 0) >= 130000
  AND ts.disparity_20 <= 120
  AND ts.rsi >= 30
  AND ts.rsi <= 70
ORDER BY 
    tt.date DESC -- 0순위: 최근에 추천된 종목부터 보이도록 날짜 정렬
    -- 1순위: 당일 시가 대비 상승률 오름차순 (덜 오른 종목부터)
    , ROUND(((ts.close - ts.open) / NULLIF(ts.open, 0)) * 100, 2) ASC
    -- 2순위: 당일 RSI 내림차순 (높은 종목부터)
    , ts.rsi DESC
    -- 3순위: 당일 거래대금 내림차순 (많이 터진 종목부터)
    , ts.trade_value DESC
    -- 4순위: Smart Money 내림차순
    , COALESCE(sm.sm_flow, 0) DESC
    -- 5순위: 기존 패턴 등급 순위
    , CASE 
        WHEN tt.pattern = '6등급 -> 4등급 -> 1등급' THEN 1
        WHEN tt.pattern = '4등급 -> 3등급 -> 1등급' THEN 2
        WHEN tt.pattern = '3등급 -> 2등급 -> 1등급' THEN 3
        ELSE 4 
    END ASC;
