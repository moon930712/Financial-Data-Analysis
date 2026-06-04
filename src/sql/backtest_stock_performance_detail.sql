/* 
  목적: 백테스트 시나리오별 최고/최악 섹터를 이끈 개별 종목들의 상세 성과 확인
  업데이트: 성과 측정 기간을 MACD 사이클(13, 26, 39일)로 변경하고 데이터 누락 방지를 위해 원본 섹터 테이블(company.master_company_list) 사용
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
    -- MACD 국면 분석
    SELECT 
        s.s_name, s.valid_s_date, s.base_seq,
        m.stock_code, m.stock_name,
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
    -- 개별 종목 수익률 계산 (13, 26, 39일 기준)
    SELECT 
        s.s_name, s.valid_s_date, s.base_seq, s.stock_code, s.stock_name, s.phase,
        CASE 
            WHEN s.phase = 1 THEN '회복기'
            WHEN s.phase = 2 THEN '상승기'
            WHEN s.phase = 3 THEN '하락기'
            WHEN s.phase = 4 THEN '둔화기'
        END as phase_name,
        ROUND(((p13.close - base.close) / NULLIF(base.close, 0)) * 100, 2) as ret_13d,
        ROUND(((p26.close - base.close) / NULLIF(base.close, 0)) * 100, 2) as ret_26d,
        ROUND(((p39.close - base.close) / NULLIF(base.close, 0)) * 100, 2) as ret_39d
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
    -- 섹터별 회복기 비중 계산 (순위용)
    SELECT 
        r.s_name, r.valid_s_date,
        si.wics_name3 as sector,
        ROUND(SUM(CASE WHEN r.phase = 1 THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as p1_ratio,
        AVG(CASE WHEN r.phase = 1 THEN r.ret_39d END) as avg_ret_39d_p1,
        AVG(CASE WHEN r.phase IN (3, 4) THEN r.ret_39d END) as avg_ret_39d_p34
    FROM stock_returns r
    JOIN company.master_company_list si ON r.stock_code = si.stock_code
    WHERE si.wics_name3 IS NOT NULL
    GROUP BY r.s_name, r.valid_s_date, si.wics_name3
    HAVING COUNT(*) >= 3
),
winner_sectors AS (
    -- 시나리오별 소분류 순위 1위(최고 모멘텀) vs 꼴찌(최저 모멘텀) 확정
    -- 기준: 회복기 비중(p1_ratio)이 가장 높은 섹터 vs 가장 낮은 섹터
    SELECT * FROM (
        SELECT s_name, '상위그룹(회복)' as grp, sector,
               ROW_NUMBER() OVER(PARTITION BY s_name ORDER BY p1_ratio DESC, avg_ret_39d_p1 DESC NULLS LAST) as rnk
        FROM sector_performance
        UNION ALL
        SELECT s_name, '하위그룹(하락/둔화)', sector,
               ROW_NUMBER() OVER(PARTITION BY s_name ORDER BY p1_ratio ASC, avg_ret_39d_p34 ASC NULLS LAST) as rnk
        FROM sector_performance
    ) t WHERE rnk = 1
)
-- 최종 결과: 승자 섹터 내의 실제 계산 대상 종목들 나열
SELECT 
    ws.s_name as "시나리오",
    ws.grp as "그룹",
    ws.sector as "대상섹터",
    sr.stock_name as "종목명",
    sr.phase_name as "당시국면",
    sr.ret_13d || '%' as "13일성적",
    sr.ret_26d || '%' as "26일성적",
    sr.ret_39d || '%' as "39일성적"
FROM winner_sectors ws
JOIN company.master_company_list si ON ws.sector = si.wics_name3
JOIN stock_returns sr ON ws.s_name = sr.s_name AND si.stock_code = sr.stock_code
WHERE (ws.grp = '상위그룹(회복)' AND sr.phase = 1)
   OR (ws.grp = '하위그룹(하락/둔화)' AND sr.phase IN (3, 4))
ORDER BY 
    ws.s_name ASC, 
    ws.grp DESC, 
    sr.ret_39d DESC;
