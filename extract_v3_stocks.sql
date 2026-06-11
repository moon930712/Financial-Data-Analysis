-- V3 필터 (과열 방지 및 추가 패턴) 적용 데일리 종목 추출 쿼리 (Grafana 연동용)
-- 조건: 거래대금 스파이크 >= 1.8, 기관/외인 3일 순매수 >= 13만, 20일 이격도 <= 120, RSI(14) <= 70

WITH target_date AS (
    SELECT 
        CASE 
            WHEN ${date:sqlstring} = '' OR ${date:sqlstring} = 'All' OR ${date:sqlstring} IS NULL 
            THEN (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02) 
            ELSE CAST(${date:sqlstring} AS DATE) 
        END AS dt
)
, valid_dates AS (
    SELECT date, ROW_NUMBER() OVER(ORDER BY date DESC) as rn
    FROM (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date <= (SELECT dt FROM target_date)
    ) t
    ORDER BY date DESC
    LIMIT 3
)
-- [1. 테마 랭킹 산출을 위한 기초 국면 작업]
, theme_histo_base AS (
    SELECT 
        m.date
        , m.stock_code
        , (m.macd - m.signal) AS histogram
        , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
    WHERE m.date <= (SELECT dt FROM target_date) 
      AND m.date >= (SELECT dt FROM target_date) - INTERVAL '30 days'
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
    WHERE date IN (SELECT date FROM valid_dates)
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
-- [2. 타겟 테마 패턴 산출 (당일 상위 20위 내)]
, theme_patterns AS (
    SELECT 
        theme_name
        , MAX(CASE WHEN d.rn = 3 THEN global_rank END) as rank_d2
        , MAX(CASE WHEN d.rn = 2 THEN global_rank END) as rank_d1
        , MAX(CASE WHEN d.rn = 1 THEN global_rank END) as rank_d0
    FROM final_ranking r
    JOIN valid_dates d ON r.date = d.date
    GROUP BY theme_name
)
, theme_grades AS (
    SELECT 
        theme_name
        , rank_d0
        , CASE WHEN rank_d2 <= 25 THEN '1등급' WHEN rank_d2 <= 50 THEN '2등급' WHEN rank_d2 <= 75 THEN '3등급' WHEN rank_d2 <= 100 THEN '4등급' WHEN rank_d2 <= 125 THEN '5등급' ELSE '6등급' END
          || ' -> ' ||
          CASE WHEN rank_d1 <= 25 THEN '1등급' WHEN rank_d1 <= 50 THEN '2등급' WHEN rank_d1 <= 75 THEN '3등급' WHEN rank_d1 <= 100 THEN '4등급' WHEN rank_d1 <= 125 THEN '5등급' ELSE '6등급' END
          || ' -> ' ||
          CASE WHEN rank_d0 <= 25 THEN '1등급' WHEN rank_d0 <= 50 THEN '2등급' WHEN rank_d0 <= 75 THEN '3등급' WHEN rank_d0 <= 100 THEN '4등급' WHEN rank_d0 <= 125 THEN '5등급' ELSE '6등급' END
          AS pattern
    FROM theme_patterns
    WHERE rank_d0 <= 20
)
, target_themes AS (
    SELECT theme_name, pattern
    FROM theme_grades
    WHERE pattern IN (
        '6등급 -> 4등급 -> 1등급',
        '4등급 -> 3등급 -> 1등급',
        '3등급 -> 2등급 -> 1등급',
        '3등급 -> 3등급 -> 1등급'
        -- '4등급 -> 2등급 -> 2등급' -- 성과가 낮아 주석 처리함. 필요시 주석 해제.
    )
)
-- [3. 종목별 V3 지표 산출 (RSI, 이격도, 거래대금 스파이크)]
, stock_indicators AS (
    SELECT 
        v1.date
        , v1.stock_code
        , v1.stock_name
        , v1.close
        , v1.trade_value
        , v2.rsi
        , v1.ma20
        , (v1.close / NULLIF(v1.ma20, 0)) * 100 AS disparity_20
        -- 과거 20일 평균 거래대금 대비 당일 스파이크 비율 계산
        , (v1.trade_value / NULLIF(AVG(v1.trade_value) OVER(PARTITION BY v1.stock_code ORDER BY v1.date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING), 0)) AS volume_spike
    FROM visual.vsl_anly_stocks_price_subindex01 v1
    JOIN visual.vsl_anly_stocks_price_subindex02 v2 ON v1.stock_code = v2.stock_code AND v1.date = v2.date
    WHERE v1.date <= (SELECT dt FROM target_date)
      AND v1.date >= (SELECT dt FROM target_date) - INTERVAL '40 days' 
)
, target_stocks AS (
    SELECT *
    FROM (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY date DESC) as rn_date
        FROM stock_indicators
    ) t
    WHERE rn_date = 1 -- 가장 최근(target_date) 기준
)
-- [4. 최근 3일 스마트머니(외인+기관 순매수) 합산]
, smart_money AS (
    SELECT 
        stock_code
        , SUM(CASE WHEN investor IN ('기관합계', '외국인') THEN net_trade_vol ELSE 0 END) as sm_flow
    FROM visual.vsl_krx_stocks_investor_shares_trading_info
    WHERE date IN (SELECT date FROM valid_dates)
    GROUP BY stock_code
)
-- [5. 최종 결과 도출 (V3 필터 적용)]
SELECT 
    to_char(ts.date, 'YYYY-MM-DD') AS "날짜"
    , tt.theme_name AS "테마명"
    , tt.pattern AS "패턴"
    , ts.stock_name AS "종목명"
--   , ts.close AS "종가"
--   , ROUND(ts.volume_spike::numeric, 2) AS "거래대금스파이크"
--  , sm.sm_flow AS "외인기관_3일순매수"
--    , ROUND(ts.disparity_20::numeric, 2) AS "20일이격도(%)"
--    , ROUND(ts.rsi::numeric, 2) AS "RSI(14)"
FROM target_themes tt
JOIN industry.theme_name_list nl ON tt.theme_name = nl.theme_name
JOIN target_stocks ts ON nl.stock_code = ts.stock_code
LEFT JOIN smart_money sm ON ts.stock_code = sm.stock_code
WHERE ts.volume_spike >= 1.8
  AND COALESCE(sm.sm_flow, 0) >= 130000
  AND ts.disparity_20 <= 120
  AND ts.rsi <= 70
ORDER BY 
    CASE 
        WHEN tt.pattern = '6등급 -> 4등급 -> 1등급' THEN 1
        WHEN tt.pattern = '4등급 -> 3등급 -> 1등급' THEN 2
        WHEN tt.pattern = '3등급 -> 2등급 -> 1등급' THEN 3
        WHEN tt.pattern = '3등급 -> 3등급 -> 1등급' THEN 4
        ELSE 5 
    END ASC
    , ts.volume_spike DESC;
