import os, psycopg2, pandas as pd

# DB 연결
[os.environ.setdefault(k,v) for line in open('.env') if '=' in line for k,v in [line.strip().split('=',1)]]
conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', 5432), dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])

# 1. 원자력 관련 핵심 종목 코드 확인
nuke_names = ['두산에너빌리티', '현대건설', '한전기술', '한전산업', '비에이치아이']
q_nuke = f"SELECT DISTINCT stock_code, stock_name FROM visual.vsl_anly_stocks_price_subindex01 WHERE stock_name IN {tuple(nuke_names)}"
nuke_df = pd.read_sql_query(q_nuke, conn)
nuke_codes = nuke_df['stock_code'].tolist()

# 2. 분석 쿼리 (분기별 PER, ROE, 거래량 집계)
# - 분기는 date_trunc('quarter', date) 사용
# - PER, ROE는 분기 평균, 거래량은 분기관 전체 합계 또는 평균 사용
sql_trend = f"""
WITH target_stocks AS (
    -- 조선, 방산 (WICS 기준) 및 원자력 (종목코드 기준) 통합
    SELECT DISTINCT stock_code, stock_name, 
           CASE WHEN wics_name = '조선' THEN '조선'
                WHEN wics_name = '우주항공과국방' THEN '방산'
                WHEN stock_code IN {tuple(nuke_codes)} THEN '원자력'
           END AS sector
    FROM visual.vsl_anly_stocks_price_subindex01
    WHERE wics_name IN ('조선', '우주항공과국방') OR stock_code IN {tuple(nuke_codes)}
),
quarterly_data AS (
    SELECT 
        ts.sector,
        date_trunc('quarter', f.date) AS quarter,
        AVG(NULLIF(f.per, 0)) AS avg_per,
        AVG(NULLIF(f.pbr, 0)) AS avg_pbr,
        -- ROE는 stock_price_subindex 테이블의 정보를 쓰거나 fundamental을 조인해야 함
        -- 여기서는 fundamental 테이블에 ROE가 있다고 가정 (없으면 mapping 정보 활용)
        AVG(NULLIF(f.per, 0)) as dummy_roe -- 실제 로직 확인 필요
    FROM company.krx_stocks_fundamental_info f
    JOIN target_stocks ts ON f.code = ts.stock_code
    WHERE f.date >= CURRENT_DATE - INTERVAL '3 years'
    GROUP BY ts.sector, date_trunc('quarter', f.date)
),
quarterly_vol AS (
    SELECT 
        ts.sector,
        date_trunc('quarter', v.date) AS quarter,
        AVG(v.volume) AS avg_vol
    FROM visual.vsl_anly_stocks_price_subindex01 v
    JOIN target_stocks ts ON v.stock_code = ts.stock_code
    WHERE v.date >= CURRENT_DATE - INTERVAL '3 years'
    GROUP BY ts.sector, date_trunc('quarter', v.date)
)
SELECT 
    d.sector, d.quarter, d.avg_per, d.avg_pbr, v.avg_vol
FROM quarterly_data d
JOIN quarterly_vol v ON d.sector = v.sector AND d.quarter = v.quarter
ORDER BY d.sector, d.quarter;
"""

print("Running trend analysis query...")
df_result = pd.read_sql_query(sql_trend, conn)
df_result.to_csv('industry_trend_data.csv', index=False)
print("Data saved to industry_trend_data.csv")
conn.close()
