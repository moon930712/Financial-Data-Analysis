-- WICS 소분류(wics_name3) 기준 국면 그룹핑(1+2, 3+4) 순환매 분석
-- 회복기(1)+하락기(2) vs 상승기(3)+둔화기(4)
WITH histo_base AS (
    SELECT 
        m.date, m.stock_code, m.stock_name,
        (m.macd - m.signal) AS histogram,
        LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
    FROM visual.vsl_anly_stocks_price_subindex02 m
),
phase_classification AS (
    SELECT 
        date, stock_code, stock_name,
        CASE 
            WHEN histogram < 0 AND histogram > lag_histogram THEN 1
            WHEN histogram < 0 AND histogram <= lag_histogram THEN 2
            WHEN histogram >= 0 AND histogram > lag_histogram THEN 3
            WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4
            ELSE 4
        END as phase
    FROM histo_base
    WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex02)
),
stock_sector_info AS (
    SELECT DISTINCT stock_code, wics_name3 as sector_name
    FROM visual.vsl_krx_stocks_cap
    WHERE wics_name3 != '미분류'
),
sector_aggregation AS (
    SELECT 
        si.sector_name, COUNT(*) as total_cnt,
        SUM(CASE WHEN p.phase IN (1, 2) THEN 1 ELSE 0 END) as g1_cnt,
        SUM(CASE WHEN p.phase IN (3, 4) THEN 1 ELSE 0 END) as g2_cnt,
        MAX(p.date) as date
    FROM stock_sector_info si
    JOIN phase_classification p ON si.stock_code = p.stock_code
    WHERE si.sector_name IS NOT NULL AND TRIM(si.sector_name) != ''
    GROUP BY si.sector_name
    HAVING COUNT(*) >= 3
),
ratio_calculation AS (
    SELECT 
        *,
        ROUND((g1_cnt::numeric / total_cnt) * 100, 2) as g1_ratio,
        ROUND((g2_cnt::numeric / total_cnt) * 100, 2) as g2_ratio
    FROM sector_aggregation
)
SELECT 
    to_char(date, 'YYYY-MM-DD') as "날짜",
    ROW_NUMBER() OVER(ORDER BY g1_ratio DESC, total_cnt DESC) as "순위",
    sector_name as "업종명(WICS소분류)",
    total_cnt as "업종전체종목수",
    g1_ratio as "0선아래(회복+하락)비율(%)",
    g2_ratio as "0선위(상승+둔화)비율(%)"
FROM ratio_calculation
ORDER BY g1_ratio DESC, total_cnt DESC, sector_name ASC;
