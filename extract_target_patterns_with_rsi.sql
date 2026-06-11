-- DBeaver에서 실행할 수 있도록 기존 타겟 패턴 추출 쿼리에 
-- D+1 ~ D+5 수익률(Return) 및 RSI(D+0 ~ D+5) 지표를 결합한 쿼리

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
        '3등급 -> 2등급 -> 1등급'
    )
)
-- [3. 종목별 V3 지표 산출 (상단 정렬용)]
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
    WHERE v1.date <= (SELECT dt FROM target_date)
      AND v1.date >= (SELECT dt FROM target_date) - INTERVAL '40 days' 
)
, target_stocks AS (
    SELECT *
    FROM (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY stock_code ORDER BY date DESC) as rn_date
        FROM stock_indicators
    ) t
    WHERE rn_date = 1
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
-- [5. 기본 결과 집합 (이후 조인을 위한 Base)]
, base_result AS (
    SELECT 
        (SELECT dt FROM target_date) AS signal_date
        , nl.stock_code
        , tt.theme_name
        , tt.pattern
        , nl.stock_name
        , CASE tpc.phase 
            WHEN 1 THEN '회복기(1국면)' 
            WHEN 3 THEN '상승기(3국면)' 
          END AS phase
        , CASE 
            WHEN ts.volume_spike >= 1.8
             AND COALESCE(sm.sm_flow, 0) >= 130000
             AND ts.disparity_20 <= 120
             AND ts.rsi <= 70
             AND ts.rsi >= 30
             AND ts.close < ts.open * 1.10
            THEN '추천종목'
            ELSE ''
          END AS v3_condition
        , ROUND(((ts.close - ts.open) / NULLIF(ts.open, 0)) * 100, 2) AS spike_percentage
        , ts.trade_value
        , ts.volume_spike
        , sm.sm_flow
        , ts.disparity_20
    FROM target_themes tt
    JOIN industry.theme_name_list nl ON tt.theme_name = nl.theme_name
    JOIN theme_phase_classification tpc 
      ON nl.stock_code = tpc.stock_code 
     AND tpc.date = (SELECT dt FROM target_date)
    LEFT JOIN target_stocks ts ON nl.stock_code = ts.stock_code
    LEFT JOIN smart_money sm ON nl.stock_code = sm.stock_code
    WHERE tpc.phase IN (1, 3)
)
-- [6. 이후 5영업일 수익률/RSI 추출을 위한 Pivot]
, future_prices AS (
    SELECT 
        b.stock_code
        , v1.date
        , v1.close
        , v2.rsi
        , ROW_NUMBER() OVER(PARTITION BY b.stock_code ORDER BY v1.date ASC) as future_rn
    FROM base_result b
    JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON b.stock_code = v1.stock_code
    JOIN visual.vsl_anly_stocks_price_subindex02 v2 ON v1.stock_code = v2.stock_code AND v1.date = v2.date
    -- signal_date(D+0) 당일을 포함하여 그 이후 데이터 6개를 가져옴
    WHERE v1.date >= b.signal_date
)
, future_pivot AS (
    SELECT 
        stock_code
        , MAX(CASE WHEN future_rn = 1 THEN close END) AS close_d0
        , MAX(CASE WHEN future_rn = 1 THEN rsi END) AS rsi_d0
        , MAX(CASE WHEN future_rn = 2 THEN close END) AS close_d1
        , MAX(CASE WHEN future_rn = 2 THEN rsi END) AS rsi_d1
        , MAX(CASE WHEN future_rn = 3 THEN close END) AS close_d2
        , MAX(CASE WHEN future_rn = 3 THEN rsi END) AS rsi_d2
        , MAX(CASE WHEN future_rn = 4 THEN close END) AS close_d3
        , MAX(CASE WHEN future_rn = 4 THEN rsi END) AS rsi_d3
        , MAX(CASE WHEN future_rn = 5 THEN close END) AS close_d4
        , MAX(CASE WHEN future_rn = 5 THEN rsi END) AS rsi_d4
        , MAX(CASE WHEN future_rn = 6 THEN close END) AS close_d5
        , MAX(CASE WHEN future_rn = 6 THEN rsi END) AS rsi_d5
    FROM future_prices
    WHERE future_rn <= 6
    GROUP BY stock_code
)
-- [7. 최종 조회]
SELECT 
    TO_CHAR(b.signal_date, 'YYYY-MM-DD') AS "Signal Date"
    , b.theme_name AS "Theme"
    , b.pattern AS "Pattern"
    , b.stock_name AS "Stock Name"
    , b.phase AS "Phase"
    , b.v3_condition AS "조건만족"
    , b.trade_value AS "거래대금"
    , ROUND(b.volume_spike, 2) AS "Volume Spike"
    , COALESCE(b.sm_flow, 0) AS "Smart Money"
    , ROUND(b.disparity_20, 2) AS "20MA 이격도"
    , b.spike_percentage AS "당일 시가 대비 상승률 (%)"
    , ROUND(((fp.close_d1 - fp.close_d0) / NULLIF(fp.close_d0, 0)) * 100, 2) AS "D+1 Return (%)"
    , ROUND(((fp.close_d2 - fp.close_d0) / NULLIF(fp.close_d0, 0)) * 100, 2) AS "D+2 Return (%)"
    , ROUND(((fp.close_d3 - fp.close_d0) / NULLIF(fp.close_d0, 0)) * 100, 2) AS "D+3 Return (%)"
    , ROUND(((fp.close_d4 - fp.close_d0) / NULLIF(fp.close_d0, 0)) * 100, 2) AS "D+4 Return (%)"
    , ROUND(((fp.close_d5 - fp.close_d0) / NULLIF(fp.close_d0, 0)) * 100, 2) AS "D+5 Return (%)"
    , ROUND(fp.rsi_d0, 2) AS "D+day rsi"
    , ROUND(fp.rsi_d1, 2) AS "D+1 rsi"
    , ROUND(fp.rsi_d2, 2) AS "D+2 rsi"
    , ROUND(fp.rsi_d3, 2) AS "D+3 rsi"
    , ROUND(fp.rsi_d4, 2) AS "D+4 rsi"
    , ROUND(fp.rsi_d5, 2) AS "D+5 rsi"
FROM base_result b
LEFT JOIN future_pivot fp ON b.stock_code = fp.stock_code
ORDER BY 
    CASE WHEN b.v3_condition = '추천종목' THEN 1 ELSE 2 END ASC
    , b.spike_percentage ASC        -- 1. 시가 대비 덜 오른 종목부터
    , fp.rsi_d0 DESC                -- 2. 당일 RSI가 높은 종목부터
    , b.trade_value DESC           -- 3. 거래대금이 많이 터진 종목부터
    , b.sm_flow DESC               -- 4. 스마트머니가 많이 들어온 종목부터
    , CASE 
        WHEN b.pattern = '6등급 -> 4등급 -> 1등급' THEN 1
        WHEN b.pattern = '4등급 -> 3등급 -> 1등급' THEN 2
        WHEN b.pattern = '3등급 -> 2등급 -> 1등급' THEN 3
        ELSE 4 
    END ASC;
