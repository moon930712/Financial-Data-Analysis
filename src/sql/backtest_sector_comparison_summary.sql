/* 
  전략: 상위 섹터(P1 종목 평균) vs 하위 섹터(P3,4 종목 평균) 성과 대조 (순위 우선 정렬 버전)
  - 순위 기준: 회복기 비중(p1_ratio)이 가장 높은 섹터(1위) vs 가장 낮은 섹터(꼴찌)
  - 성과 측정: 13, 26, 39일 (MACD 사이클)
*/
WITH trading_calendar AS (
    SELECT date, ROW_NUMBER() OVER(ORDER BY date) as seq
    FROM (SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01) d
),
scenarios_input AS (
    SELECT 'A. 밸류업 초입' as s_name, '2024-02-01'::date as s_date UNION ALL
    SELECT 'B. 블랙 먼데이' as s_name, '2024-08-05'::date as s_date UNION ALL
    SELECT 'C. 정치적 저점' as s_name, '2025-04-09'::date as s_date UNION ALL
    SELECT 'D. 임계점 돌파' as s_name, '2025-10-01'::date as s_date UNION ALL
    SELECT 'E. 최근 4개월' as s_name, (SELECT MAX(date) - INTERVAL '4 month' FROM visual.vsl_anly_stocks_price_subindex01)::date as s_date
),
scenarios AS (
    SELECT si.s_name, tc.date as valid_s_date, tc.seq as base_seq
    FROM scenarios_input si
    JOIN trading_calendar tc ON tc.date = (SELECT MIN(date) FROM trading_calendar WHERE date >= si.s_date)
),
phase_data AS (
    SELECT 
        s.s_name, s.valid_s_date, s.base_seq,
        m.stock_code, 
        CASE 
            WHEN (m.macd - m.signal) < 0 AND (m.macd - m.signal) > LAG(m.macd - m.signal) OVER(PARTITION BY m.stock_code ORDER BY m.date) THEN 1
            WHEN (m.macd - m.signal) >= 0 AND (m.macd - m.signal) > LAG(m.macd - m.signal) OVER(PARTITION BY m.stock_code ORDER BY m.date) THEN 2
            WHEN (m.macd - m.signal) < 0 AND (m.macd - m.signal) <= LAG(m.macd - m.signal) OVER(PARTITION BY m.stock_code ORDER BY m.date) THEN 3
            WHEN (m.macd - m.signal) >= 0 AND (m.macd - m.signal) <= LAG(m.macd - m.signal) OVER(PARTITION BY m.stock_code ORDER BY m.date) THEN 4
            ELSE 4
        END as phase,
        m.date as price_date
    FROM scenarios s
    JOIN visual.vsl_anly_stocks_price_subindex02 m ON m.date <= s.valid_s_date
),
snapshots AS (
    SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY s_name, stock_code ORDER BY price_date DESC) as rn 
        FROM phase_data
    ) t WHERE rn = 1
),
stock_returns AS (
    -- 13, 26, 39일 수익률 계산
    SELECT 
        s.s_name, s.valid_s_date, s.stock_code, s.phase,
        ((p13.close - base.close) / NULLIF(base.close, 0)) * 100 as ret_13d,
        ((p26.close - base.close) / NULLIF(base.close, 0)) * 100 as ret_26d,
        ((p39.close - base.close) / NULLIF(base.close, 0)) * 100 as ret_39d
    FROM snapshots s
    JOIN visual.vsl_anly_stocks_price_subindex01 base ON s.stock_code = base.stock_code AND s.valid_s_date = base.date
    LEFT JOIN trading_calendar tc13 ON tc13.seq = s.base_seq + 13
    LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p13 ON s.stock_code = p13.stock_code AND p13.date = tc13.date
    LEFT JOIN trading_calendar tc26 ON tc26.seq = s.base_seq + 26
    LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p26 ON s.stock_code = p26.stock_code AND p26.date = tc26.date
    LEFT JOIN trading_calendar tc39 ON tc39.seq = s.base_seq + 39
    LEFT JOIN visual.vsl_anly_stocks_price_subindex01 p39 ON s.stock_code = p39.stock_code AND p39.date = tc39.date
),
sector_performance AS (
    SELECT 
        r.s_name, r.valid_s_date,
        si.wics_name3 as sector,
        COUNT(*) as total_stocks,
        ROUND(SUM(CASE WHEN r.phase = 1 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as p1_ratio,
        AVG(CASE WHEN r.phase = 1 THEN r.ret_13d END) as ret_13d_p1,
        AVG(CASE WHEN r.phase = 1 THEN r.ret_26d END) as ret_26d_p1,
        AVG(CASE WHEN r.phase = 1 THEN r.ret_39d END) as ret_39d_p1,
        AVG(CASE WHEN r.phase IN (3, 4) THEN r.ret_13d END) as ret_13d_p34,
        AVG(CASE WHEN r.phase IN (3, 4) THEN r.ret_26d END) as ret_26d_p34,
        AVG(CASE WHEN r.phase IN (3, 4) THEN r.ret_39d END) as ret_39d_p34
    FROM stock_returns r
    JOIN company.master_company_list si ON r.stock_code = si.stock_code
    WHERE si.wics_name3 IS NOT NULL
    GROUP BY r.s_name, r.valid_s_date, si.wics_name3
    HAVING COUNT(*) >= 3
),
winners AS (
    -- 시나리오별 소분류 순위 1위(최고 모멘텀) vs 꼴찌(최저 모멘텀) 확정
    SELECT * FROM (
        SELECT s_name, valid_s_date, 'TOP_RANK' as grp, sector, p1_ratio, 
               ret_13d_p1 as r13, ret_26d_p1 as r26, ret_39d_p1 as r39,
               ROW_NUMBER() OVER(PARTITION BY s_name ORDER BY p1_ratio DESC, ret_39d_p1 DESC NULLS LAST) as rnk
        FROM sector_performance
        UNION ALL
        SELECT s_name, valid_s_date, 'BOTTOM_RANK', sector, p1_ratio, 
               ret_13d_p34 as r13, ret_26d_p34 as r26, ret_39d_p34 as r39,
               ROW_NUMBER() OVER(PARTITION BY s_name ORDER BY p1_ratio ASC, ret_39d_p34 ASC NULLS LAST) as rnk
        FROM sector_performance
    ) t WHERE rnk <= 3
)
SELECT 
    w1.s_name as "시나리오",
    w1.rnk as "순위",
    w1.sector as "상위섹터(회복비중최고)",
    w1.p1_ratio || '%' as "회복비중",
    ROUND(w1.r13::numeric, 2) || '%' as "13일",
    ROUND(w1.r26::numeric, 2) || '%' as "26일",
    ROUND(w1.r39::numeric, 2) || '%' as "39일",
    w2.sector as "하위섹터(회복비중최저)",
    w2.p1_ratio || '%' as "회복비중 ",
    ROUND(w2.r13::numeric, 2) || '%' as "13일 ",
    ROUND(w2.r26::numeric, 2) || '%' as "26일 ",
    ROUND(w2.r39::numeric, 2) || '%' as "39일 "
FROM winners w1
JOIN winners w2 ON w1.s_name = w2.s_name AND w1.rnk = w2.rnk AND w1.grp = 'TOP_RANK' AND w2.grp = 'BOTTOM_RANK'
ORDER BY w1.valid_s_date ASC, w1.rnk ASC;
