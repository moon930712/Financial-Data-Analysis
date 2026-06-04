import psycopg2, os
import pandas as pd
from tabulate import tabulate

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
load_env()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

query = """
WITH theme_data AS (
    -- 1. 테마별 최신 PBR 및 ROE 정보 취합
    SELECT 
        nt.theme_name
        , nt.stock_code
        , rb.roe
        , fb.pbr
    FROM company.naver_theme nt
    JOIN (
        SELECT koreanname, roe FROM company.kis_kospi_info
        UNION ALL
        SELECT koreanname, roe FROM company.kis_kosdaq_info
    ) rb ON nt.stock_name = rb.koreanname
    LEFT JOIN company.krx_stocks_fundamental_info fb ON nt.stock_code = fb.code
    WHERE fb.date = (SELECT MAX(date) FROM company.krx_stocks_fundamental_info)
      AND rb.roe IS NOT NULL AND rb.roe > 0
),
theme_stats AS (
    -- 2. 테마별 통계 계산
    SELECT 
        theme_name
        , PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY roe) as median_roe
        , AVG(pbr) as avg_pbr
        , COUNT(DISTINCT stock_code) as stock_count
    FROM theme_data
    GROUP BY theme_name
)
-- 3. 최종 결과: 가성비(Efficiency) 순위
SELECT 
    ROW_NUMBER() OVER(ORDER BY (avg_pbr / NULLIF(median_roe, 0)) ASC) AS rank
    , theme_name
    , ROUND(median_roe::numeric, 2) as roe_median
    , ROUND(avg_pbr::numeric, 2) as pbr_avg
    , ROUND((avg_pbr / NULLIF(median_roe, 0))::numeric, 4) as pbr_per_roe
    , stock_count
FROM theme_stats
WHERE median_roe > 0
  AND stock_count > 5
ORDER BY pbr_per_roe ASC
LIMIT 15;
"""

import sys
import io

# Set encoding to utf-8 for console output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    conn = get_connection()
    df = pd.read_sql(query, conn)
    print("\n[ 샘플 확인: 네이버 테마 기반 가성비 순위 (Top 15) ]")
    # Tabulate can sometimes have issues with wide characters, but let's try
    print(df.to_string(index=False))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
