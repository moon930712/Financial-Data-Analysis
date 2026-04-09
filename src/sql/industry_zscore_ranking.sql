-- =====================================================================
-- 퀀트 스크리닝 및 업종별 다중 요인(Multi-Factor) Z-Score 통합 랭킹 모델 (심플 업종 중심 버전)
-- 작성 목적: 복잡한 개별 종목 지표 대신 업종 전체의 과거 3년 평균 데이터와 
--            최근 1개월 수급(거래량) 모멘텀을 결합한 가볍고 강력한 랭킹 시스템
-- =====================================================================

WITH latest_date AS (
    -- 1. 가장 최근 영업일 추출 (하나의 기준으로 통일)
    SELECT MAX(date) AS max_d 
    FROM visual.vsl_anly_stocks_price_subindex01
),
industry_mapping AS (
    -- 2. 최신 기준의 종목별 WICS 업종 및 ROE 정보 매핑
    SELECT 
        v.stock_code, 
        COALESCE(v.wics_name, '기타') AS industry,
        -- ROE 문자열 캐스팅 오류 방지
        COALESCE(NULLIF(trim(ci.roe::text), ''), '-5.0')::numeric AS roe
    FROM visual.vsl_anly_stocks_price_subindex01 v
    JOIN (
        SELECT shortcode AS stock_code, roe FROM company.kis_kospi_info
        UNION ALL
        SELECT shortcode AS stock_code, roe FROM company.kis_kosdaq_info
    ) ci ON v.stock_code = ci.stock_code
    WHERE v.date = (SELECT max_d FROM latest_date)
),
industry_historical_stats AS (
    -- 3. 업종별 과거 1년 평균 PBR 및 ROE 집계
    SELECT 
        m.industry,
        AVG(NULLIF(f.pbr, 0)) AS avg_pbr_1yr,
        AVG(m.roe) AS sector_avg_roe
    FROM company.krx_stocks_fundamental_info f
    JOIN industry_mapping m ON f.code = m.stock_code
    WHERE f.date >= (SELECT max_d FROM latest_date) - INTERVAL '1 year'
    GROUP BY m.industry
),
industry_current_stats AS (
    -- 4. 업종별 최근 1개월 평균 PBR 집계 및 종목 수 필터링
    SELECT 
        m.industry,
        COUNT(DISTINCT m.stock_code) AS stock_count,
        AVG(NULLIF(f.pbr, 0)) AS avg_pbr_1m
    FROM company.krx_stocks_fundamental_info f
    JOIN industry_mapping m ON f.code = m.stock_code
    WHERE f.date >= (SELECT max_d FROM latest_date) - INTERVAL '1 month'
    GROUP BY m.industry
    HAVING COUNT(DISTINCT m.stock_code) >= 5
),
industry_volume_momentum AS (
    -- 5. 최근 1개월 vs 이전 3개월 평균 거래량 비교
    SELECT 
        wics_name AS industry,
        AVG(CASE WHEN date >= (SELECT max_d FROM latest_date) - INTERVAL '1 month' THEN volume ELSE NULL END) AS vol_recent_1m,
        AVG(CASE WHEN date < (SELECT max_d FROM latest_date) - INTERVAL '1 month' 
                 AND date >= (SELECT max_d FROM latest_date) - INTERVAL '4 months' THEN volume ELSE NULL END) AS vol_prev_3m
    FROM visual.vsl_anly_stocks_price_subindex01
    GROUP BY wics_name
),
industry_metrics AS (
    -- 6. 핵심 지표 결합
    SELECT 
        c.industry,
        c.stock_count,
        h.sector_avg_roe as avg_roe,
        COALESCE(c.avg_pbr_1m / NULLIF(h.avg_pbr_1yr, 0), 1.0) AS pbr_discount_ratio,
        COALESCE(v.vol_recent_1m / NULLIF(v.vol_prev_3m, 0), 1.0) AS volume_growth_ratio
    FROM industry_current_stats c
    JOIN industry_historical_stats h ON c.industry = h.industry
    JOIN industry_volume_momentum v ON c.industry = v.industry
),
zscore_calculation AS (
    -- 7. 표준점수(Z-Score) 산출
    SELECT 
        industry,
        stock_count,
        avg_roe,
        pbr_discount_ratio,
        volume_growth_ratio,
        COALESCE((avg_roe - AVG(avg_roe) OVER()) / NULLIF(STDDEV_POP(avg_roe) OVER(), 0), 0) AS z_fundamental,
        COALESCE(((pbr_discount_ratio - AVG(pbr_discount_ratio) OVER()) / NULLIF(STDDEV_POP(pbr_discount_ratio) OVER(), 0)) * -1, 0) AS z_value,
        COALESCE((volume_growth_ratio - AVG(volume_growth_ratio) OVER()) / NULLIF(STDDEV_POP(volume_growth_ratio) OVER(), 0), 0) AS z_momentum
    FROM industry_metrics
)
-- 8. 종합 순위 공개
SELECT 
    ROW_NUMBER() OVER(ORDER BY ((z_momentum * 0.4) + (z_value * 0.3) + (z_fundamental * 0.3)) DESC) AS "종합 순위(Rank)",
    industry AS "업종명(WICS)",
/*
    ROUND(((z_momentum * 0.5) + (z_value * 0.2) + (z_fundamental * 0.3))::numeric, 2) AS "통합 Z-Score",
    ROUND(z_momentum::numeric, 2) AS "Z-Score (수급 활력)",
    ROUND(z_value::numeric, 2) AS "Z-Score (수치적 저평가)",
    ROUND(z_fundamental::numeric, 2) AS "Z-Score (기초 수익성)",
    stock_count AS "소속 종목 수",
    ROUND(avg_roe::numeric, 2) AS "업종 평균 ROE",
    ROUND(pbr_discount_ratio::numeric, 2) AS "1년 평균 대비 1개월 PBR 비율",
*/
    ROUND(volume_growth_ratio::numeric, 2) AS "최근 1개월 거래량 증가율"
FROM zscore_calculation
ORDER BY "종합 순위(Rank)";
