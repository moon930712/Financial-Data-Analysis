-- =====================================================================
-- 퀀트 스크리닝 및 업종별 다중 요인(Multi-Factor) Z-Score 통합 랭킹 모델
-- 작성 목적: Python Pandas 의존성 없이 PostgreSQL Native Query 만으로 
--            종목 단위의 과거 3년 시계열 처리 및 업종 Z-Score를 산출하는 파이프라인
-- (참고: 기초 업종분류는 visual.vsl_anly_stocks_price_subindex01 사용)
-- =====================================================================
WITH latest_date AS (
    -- 1. 가장 최근 영업일 추출
    SELECT MAX(date) AS max_d 
    FROM company.krx_stocks_fundamental_info
),
historical_stats AS (
    -- 2. 개별 종목별 과거 3년 평균 PBR 및 PER 집계
    SELECT 
        code,
        AVG(NULLIF(per, 0)) AS avg_per_3yr,
        AVG(NULLIF(pbr, 0)) AS avg_pbr_3yr
    FROM company.krx_stocks_fundamental_info
    WHERE date >= (SELECT max_d FROM latest_date) - INTERVAL '3 years'
    GROUP BY code
),
current_stats AS (
    -- 3. 최근 영업일 기준 개별 종목 펀더멘탈
    SELECT 
        code, per, pbr
    FROM company.krx_stocks_fundamental_info
    WHERE date = (SELECT max_d FROM latest_date)
),
market_info AS (
    -- 4. 비주얼라이징 데일리 팩터 테이블에서 최신 기준의 종목명 및 WICS 분류 추출
    SELECT DISTINCT stock_code, stock_name, wics_name
    FROM visual.vsl_anly_stocks_price_subindex01
    WHERE date = (SELECT MAX(date) FROM visual.vsl_anly_stocks_price_subindex01)
),
combined_stock_data AS (
    -- 5. 종목별 기초 통계 및 펀더멘탈 결합 (PBR_Discount 및 근사 ROE 도출)
    SELECT 
        m.stock_code,
        m.stock_name,
        COALESCE(m.wics_name, '기타') AS industry,
        -- ROE 역산: PBR = PER * ROE => ROE = PBR / PER
        -- 적자 기업이거나 PER 계산이 불가한 경우 패널티(-5.0) 부여
        CASE 
            WHEN c.per > 0 AND c.per IS NOT NULL 
            THEN (c.pbr / c.per) * 100 
            ELSE -5.0 
        END AS roe,
        -- PBR 할인율 (Value): (Current PBR) / (3yr Avg PBR) 
        CASE 
            WHEN h.avg_pbr_3yr > 0 THEN c.pbr / h.avg_pbr_3yr
            ELSE NULL 
        END AS pbr_discount_ratio,
        -- 저평가 여부 플래그 지정 (현재 PBR <= 3년 평균의 90% & 현재 PBR < 1.5)
        CASE 
            WHEN c.pbr <= (h.avg_pbr_3yr * 0.9) AND c.pbr < 1.5 THEN 1.0
            ELSE 0.0 
        END AS is_undervalued
    FROM market_info m
    JOIN current_stats c ON m.stock_code = c.code
    JOIN historical_stats h ON m.stock_code = h.code
    WHERE m.wics_name IS NOT NULL
),
industry_aggregation AS (
    -- 6. 업종(Industry)별 팩터 집계
    SELECT 
        industry,
        COUNT(stock_code) AS stock_count,
        AVG(roe) AS avg_roe,                                 -- Factor 1: Fundamental
        AVG(pbr_discount_ratio) AS avg_pbr_discount,         -- Factor 2: Value
        SUM(is_undervalued) AS undervalued_count
    FROM combined_stock_data
    GROUP BY industry
    HAVING COUNT(stock_code) >= 5  -- 테마성 소규모 업종 제외
),
industry_metrics AS (
    -- 7. 집계된 데이터를 기반으로 밀집도(Density) 계산
    SELECT 
        industry,
        stock_count,
        avg_roe,
        avg_pbr_discount,
        undervalued_count,
        (undervalued_count / stock_count::numeric) * 100 AS undervalue_density -- Factor 3: Quality
    FROM industry_aggregation
),
zscore_calculation AS (
    -- 8. 윈도우 함수(Window Function)를 이용한 Z-Score 산출
    SELECT 
        industry,
        stock_count,
        undervalue_density,
        avg_pbr_discount,
        avg_roe,
        -- Z-Score 계산
        COALESCE((avg_roe - AVG(avg_roe) OVER()) / NULLIF(STDDEV_POP(avg_roe) OVER(), 0), 0) AS z_fundamental,
        -- PBR 할인율은 역수 처리 음수화(-1)
        COALESCE(((avg_pbr_discount - AVG(avg_pbr_discount) OVER()) / NULLIF(STDDEV_POP(avg_pbr_discount) OVER(), 0)) * -1, 0) AS z_value,
        COALESCE((undervalue_density - AVG(undervalue_density) OVER()) / NULLIF(STDDEV_POP(undervalue_density) OVER(), 0), 0) AS z_density
    FROM industry_metrics
)
-- 9. 최종 종순위 산출 및 랭킹 정렬
SELECT 
    ROW_NUMBER() OVER(ORDER BY ((z_density * 0.4) + (z_value * 0.3) + (z_fundamental * 0.3)) DESC) AS "종합 순위(Rank)",
    industry AS "섹터명(WICS)",
    ROUND(((z_density * 0.4) + (z_value * 0.3) + (z_fundamental * 0.3))::numeric, 2) AS "통합 Z-Score (Total Score)",
    ROUND(z_density::numeric, 2) AS "Z-Score (저평가 밀집도)",
    ROUND(z_value::numeric, 2) AS "Z-Score (수치적 저평가)",
    ROUND(z_fundamental::numeric, 2) AS "Z-Score (기초 펀더멘탈)",
    stock_count AS "소속 종목 수",
    ROUND(undervalue_density::numeric, 2) || '%' AS "저평가 종목 밀집율(%)",
    ROUND(avg_pbr_discount::numeric, 2) AS "업종 평균 3년 대비 할인율"
FROM zscore_calculation
ORDER BY "통합 Z-Score (Total Score)" DESC;
