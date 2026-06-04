WITH industry_data AS (
    -- 1. 업종별 최신 PBR 및 ROE 정보 취합 (가격 테이블에서도 최신 날짜만 필터링)
    SELECT 
        ib.wics_name
        , ib.stock_code
        , rb.roe
        , fb.pbr
    FROM visual.vsl_anly_stocks_price_subindex01 ib
    JOIN (
        SELECT koreanname , roe FROM company.kis_kospi_info
        UNION ALL
        SELECT koreanname , roe FROM company.kis_kosdaq_info
    ) rb ON ib.stock_name = rb.koreanname
    LEFT JOIN company.krx_stocks_fundamental_info fb ON ib.stock_code = fb.code
    WHERE fb.date = (SELECT MAX(date) FROM company.krx_stocks_fundamental_info)
      AND ib.date = fb.date -- ★ 가격 데이터도 동일한 최신 날짜로 일치시킴 (중복 방지)
      AND rb.roe IS NOT NULL AND rb.roe > 0 -- 이익이 나는 기업만 대상 (가치 함정 방지)
),
sector_stats AS (
    -- 2. 업종별 중앙값 및 정확한 종목 수 요약
    SELECT 
        wics_name
        , PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY roe) as median_roe
        , AVG(pbr) as avg_pbr
        , COUNT(DISTINCT stock_code) as stock_count -- ★ 중복 없는 종목 수 계산
    FROM industry_data
    GROUP BY wics_name
),
pbr_history AS (
    -- 3. 최근 1년 업종별 PBR 밴드 (최고/최저) 계산
    SELECT 
        ib.wics_name
        , MIN(fb.pbr) as pbr_min
        , MAX(fb.pbr) as pbr_max
    FROM visual.vsl_anly_stocks_price_subindex01 ib
    JOIN company.krx_stocks_fundamental_info fb ON ib.stock_code = fb.code
    WHERE fb.date >= (CURRENT_DATE - INTERVAL '1 year')
      AND ib.date = fb.date -- ★ 과거 데이터에서도 일치시킴
    GROUP BY ib.wics_name
)
-- 4. 최종 결과: 가성비(Efficiency) 순위 도출
SELECT 
    ROW_NUMBER() OVER(ORDER BY (s.avg_pbr / NULLIF(s.median_roe, 0)) ASC) AS "순위"
    , s.wics_name AS "업종명(WICS)"
    , ROUND(s.median_roe::numeric, 2) as "ROE(중앙값)"
    , ROUND(s.avg_pbr::numeric, 2) as "현재 PBR"
    -- ROE 1%당 지불하는 PBR (낮을수록 가성비 좋음)
    , ROUND((s.avg_pbr / NULLIF(s.median_roe, 0))::numeric, 4) as "PBR_per_ROE"
    -- 최근 1년 고점/저점 대비 현재 위치 (%)
    , ROUND(((s.avg_pbr - h.pbr_min) / NULLIF(h.pbr_max - h.pbr_min, 0) * 100)::numeric, 1) as "밴드_현재위치(%)"
    , s.stock_count as "종목수"
FROM sector_stats s
JOIN pbr_history h ON s.wics_name = h.wics_name
WHERE 1=1
  AND s.median_roe > 0
--  and s.wics_name IN ($wics_name)
  AND s.stock_count > 5 -- ★ 종목수 5개 초과 업종만 반영 (사용자 요청 사항)
ORDER BY "PBR_per_ROE" ASC; -- 가성비가 좋은(ROE 대비 PBR이 싼) 순서로 정렬
