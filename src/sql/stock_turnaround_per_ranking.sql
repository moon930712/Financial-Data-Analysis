-- [전 업종 PER 기반 턴어라운드 종목 선정 모델]
-- 1. 가치(PER) + 2. 수익성(ROE) + 3. 수급(Volume) + 4. 리포트(Burst) + 5. 심리(Sentiment)

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
report_stats AS (
    -- 2-1. 리포트 동시 폭발 (최근 30일간 발행된 리포트 수 집계)
    SELECT 
        code AS stock_code,
        COUNT(*) AS report_count
    FROM llm.naver_stock_report
    WHERE date BETWEEN (SELECT max_date - INTERVAL '30 days' FROM latest_date) AND (SELECT max_date FROM latest_date)
    GROUP BY code
),
base_data AS (
    -- 3. 기본 정보 및 가치 지표, 거래량 모멘텀, 리포트 빈도 결합
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
        CASE WHEN vs.vol_12w_avg > 0 THEN vs.vol_last_1w / vs.vol_12w_avg ELSE 0 END AS vol_momentum,
        COALESCE(r.report_count, 0) AS report_count
    FROM visual.vsl_anly_stocks_price_subindex01 s1
    JOIN volume_stats vs ON s1.stock_code = vs.stock_code AND s1.date = vs.date
    LEFT JOIN report_stats r ON s1.stock_code = r.stock_code
    LEFT JOIN company.krx_stocks_fundamental_info f ON s1.stock_code = f.code AND s1.date = f.date
    LEFT JOIN (
        SELECT 
            CASE WHEN shortcode LIKE 'F%' THEN SUBSTRING(shortcode, 2) ELSE shortcode END AS stock_code,
            roe,
            'KOSPI' AS market_type
        FROM company.kis_kosapi_info
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
    -- 5. 투자의견 점수화 (최근 1개월 이내 리포트 기준)
    SELECT 
        code AS stock_code,
        MAX(CASE 
            WHEN inv_opi IN ('시장평균', 'Hold', '중립', 'MarketPerform', '투자의견없음', '없음', 'Neutral',
                             '매도', 'Sell', 'UnderPerform', 'MarketUnderPerform', '시장수익률하회', '비중축소', 'Reduce') THEN 1 
            ELSE 0 
        END) AS has_sell_opinion
    FROM llm.naver_stock_report
    WHERE date >= (SELECT max_date - INTERVAL '1 months' FROM latest_date)
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
        (PERCENT_RANK() OVER (ORDER BY invest_senti ASC)) * 100 AS senti_rank_score,
        (PERCENT_RANK() OVER (ORDER BY vol_momentum ASC)) * 100 AS vol_rank_score,
        (PERCENT_RANK() OVER (ORDER BY report_count ASC)) * 100 AS report_rank_score,
        -- 업종 내 상대 PER 점수: 적자 기업(per<=0)은 0점에 수렴하도록 처리
        (PERCENT_RANK() OVER (PARTITION BY wics_name ORDER BY (CASE WHEN per > 0 THEN per ELSE 999999 END) DESC)) * 100 AS industry_rel_per_score
    FROM scoring_base
    WHERE has_sell_opinion != 1 -- 매도 의견 종목 제외
)
-- 8. 최종 랭킹 산출
SELECT 
    TO_CHAR(date,'YYYY-MM-DD') AS 추천일자,
    wics_name AS "업종명",
    stock_code AS "종목코드",
    market_type AS "시장구분",
    stock_name AS "종목명",
    per AS "PER",
    roe AS "ROE",
    report_count AS "리포트수",
    -- 사용자 확정 가중치 (가치 20% + 수익성 20% + 수급 30% + 심리 10% + 리포트 20%)
    ROUND(
        (
            (industry_rel_per_score * 0.2) + -- 가치 (20%)
            (roe_rank_score * 0.2) +          -- 수익성 (20%)
            (vol_rank_score * 0.3) +          -- 수급 (30%)
            (senti_rank_score * 0.1) +         -- 심리 (10%)
            (report_rank_score * 0.2)         -- 리포트 폭발 (20%)
        )::numeric
    , 2) AS "최종 턴어라운드 점수"
FROM final_scoring
WHERE 1=1 
    AND wics_name IN ($wics_name)
ORDER BY "최종 턴어라운드 점수" DESC;
