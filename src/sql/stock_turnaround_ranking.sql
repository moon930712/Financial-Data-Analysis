-- [전 업종 가치 턴어라운드 종목 선정 모델]
-- 1. 가치(PBR, DIV) + 2. 수익성(ROE) + 3. 심리(Invest_Senti) + 4. 미래(Report)

WITH latest_date AS (
    -- 1. 가장 최신 영업일 추출
    SELECT MAX(date) AS max_date 
    FROM visual.vsl_anly_stocks_price_subindex01
),
volume_stats AS (
    -- 2. 거래량 모멘텀 계산 (최근 1주 vs 과거 12주)
    SELECT 
        stock_code,
        date,
        volume,
        AVG(volume) OVER (PARTITION BY stock_code ORDER BY date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS vol_last_1w,
        AVG(volume) OVER (PARTITION BY stock_code ORDER BY date ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING) AS vol_12w_avg
    FROM visual.vsl_anly_stocks_price_subindex01
    WHERE date >= (SELECT max_date - INTERVAL '6 months' FROM latest_date)
),
base_data AS (
    -- 3. 기본 정보 및 가치 지표, 거래량 모멘텀 결합
    SELECT 
        s1.date,
        s1.stock_code,
        s1.stock_name,
        s1.wics_name,
        f.pbr,
        f.per,
        COALESCE(k.roe, 0) AS roe,
        k.market_type,
        -- 거래량 모멘텀: 최근 1주 / 과거 12주 평균
        CASE WHEN vs.vol_12w_avg > 0 THEN vs.vol_last_1w / vs.vol_12w_avg ELSE 0 END AS vol_momentum
    FROM visual.vsl_anly_stocks_price_subindex01 s1
    JOIN volume_stats vs ON s1.stock_code = vs.stock_code AND s1.date = vs.date
    LEFT JOIN company.krx_stocks_fundamental_info f ON s1.stock_code = f.code AND s1.date = f.date
    LEFT JOIN (
        SELECT 
            -- 'F000020' 형식인 경우 숫자만 추출하거나 매칭
            CASE WHEN shortcode LIKE 'F%' THEN SUBSTRING(shortcode, 2) ELSE shortcode END AS stock_code,
            roe,
            'KOSPI' AS market_type
        FROM company.kis_kospi_info
        UNION ALL
        SELECT 
            shortcode AS stock_code, 
            roe,
            'KOSDAQ' AS market_type
        FROM company.kis_kosdaq_info
    ) k ON s1.stock_code = k.stock_code
    WHERE s1.date = (SELECT max_date FROM latest_date)
),
sentiment_data AS (
    -- 4. 투자심리 데이터 결합
    SELECT 
        date,
        stock_code,
        invest_senti
    FROM visual.vsl_anly_stocks_price_subindex03
    WHERE date = (SELECT max_date FROM latest_date)
),
analyst_data AS (
    -- 5. 투자의견 점수화 (최근 3개월 이내 리포트 기준)
    SELECT 
        code AS stock_code,
        -- 국내 증권가 특성상 'Hold(중립)'도 사실상 매도 의견으로 취급하여 1(위험)로 필터링
        MAX(CASE 
            WHEN inv_opi IN ('시장평균', 'Hold', '중립', 'MarketPerform', '투자의견없음', '없음', 'Neutral',
            				 '매도', 'Sell', 'UnderPerform', 'MarketUnderPerform', '시장수익률하회', '비중축소', 'Reduce') THEN 1 
            ELSE 0 
        END) AS has_sell_opinion
    FROM llm.naver_stock_report
    WHERE date >= (SELECT max_date - INTERVAL '3 months' FROM latest_date)
    GROUP BY code
),
scoring_base AS (
    -- 6. 모든 데이터 결합
    SELECT 
        b.*,
        COALESCE(s.invest_senti, 0) AS invest_senti,
        COALESCE(a.has_sell_opinion, 0) AS has_sell_opinion
    FROM base_data b
    LEFT JOIN sentiment_data s ON b.stock_code = s.stock_code
    LEFT JOIN analyst_data a ON b.stock_code = a.stock_code
),
final_scoring AS (
    -- 7. 각 지표별 점수 산출 (백분위 순위)
    SELECT 
        *,
        (PERCENT_RANK() OVER (ORDER BY roe ASC)) * 100 AS roe_rank_score,
        (PERCENT_RANK() OVER (ORDER BY pbr DESC)) * 100 AS pbr_rank_score, -- 낮은게 좋으므로 역순
        (PERCENT_RANK() OVER (ORDER BY invest_senti ASC)) * 100 AS senti_rank_score,
        (PERCENT_RANK() OVER (ORDER BY vol_momentum ASC)) * 100 AS vol_rank_score,
        (PERCENT_RANK() OVER (PARTITION BY wics_name ORDER BY pbr DESC)) * 100 AS industry_rel_pbr_score
    FROM scoring_base
    WHERE pbr > 0 AND pbr < 10 -- 이상치 제거
      AND has_sell_opinion != 1 -- 매도 의견이 있는 종목만 제외 (리포트 없는 소외주도 포함)
)
-- 8. 최종 랭킹 산출
SELECT 
    TO_CHAR(date,'YYYY-MM-DD') AS 추천일자,
    wics_name AS "업종명",
    stock_code AS "종목코드",
    market_type AS "시장구분",
    stock_name AS "종목명",
    ROW_NUMBER() OVER(PARTITION BY wics_name ORDER BY pbr ASC, per ASC) AS "업종내_가치순위",
    /*
    pbr AS "PBR",
    roe AS "ROE",
    invest_senti AS "투자심리",
    ROUND(vol_momentum::numeric, 2) AS "거래량모멘텀",
    */
    -- 가중치 합산 (가치 40% + 수익성 20% + 심리/수급 20% + 미래 20%)
    ROUND(
        (
            (pbr_rank_score * 0.2 + industry_rel_pbr_score * 0.4) + -- 가치 (PBR 40%)
            (roe_rank_score * 0.2) + -- 수익성 (ROE 20%)
            (senti_rank_score * 0.1 + vol_rank_score * 0.1) -- 심리/수급 (20%)
        )::numeric
    , 2) AS "최종 턴어라운드 점수"
FROM final_scoring
where 1=1 
	and wics_name IN ($wics_name)
ORDER BY "최종 턴어라운드 점수" DESC;
