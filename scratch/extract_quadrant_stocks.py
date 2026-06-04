import os
import psycopg2
import pandas as pd

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

def extract_quadrant_samples():
    conn = get_connection()
    
    # 2024-04-01 기준
    target_date = '2024-04-01'
    future_date = '2025-04-01'
    
    query = f"""
    WITH industry_base AS (
        SELECT DISTINCT stock_code, stock_name, wics_name
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{target_date}'
    ),
    fundamental_base AS (
        SELECT code AS stock_code, pbr
        FROM company.krx_stocks_fundamental_info
        WHERE date = '{target_date}'
    ),
    roe_base AS (
        SELECT koreanname AS stock_name, roe 
        FROM company.kis_kospi_info
        UNION ALL
        SELECT koreanname AS stock_name, roe 
        FROM company.kis_kosdaq_info
    ),
    price_start AS (
        SELECT stock_code, close as price_start
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{target_date}'
    ),
    price_end AS (
        SELECT stock_code, close as price_end
        FROM visual.vsl_anly_stocks_price_subindex01
        WHERE date = '{future_date}'
    )
    SELECT 
        ib.stock_name
        , ib.wics_name
        , rb.roe
        , fb.pbr
        , (pe.price_end / ps.price_start - 1) * 100 as return_1yr
    FROM industry_base ib
    JOIN roe_base rb ON ib.stock_name = rb.stock_name
    JOIN fundamental_base fb ON ib.stock_code = fb.stock_code
    JOIN price_start ps ON ib.stock_code = ps.stock_code
    JOIN price_end pe ON ib.stock_code = pe.stock_code
    WHERE rb.roe > -50 AND rb.roe < 100 
      AND fb.pbr > 0 AND fb.pbr < 20
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 중앙값 도출
    pbr_median = df['pbr'].median()
    roe_median = df['roe'].median()
    
    print(f"기준선 - PBR 중앙값: {pbr_median:.2f}, ROE 중앙값: {roe_median:.2f}\n")
    
    # 사분면 정의
    quadrants = {
        '1사분면 (Golden Area: 저평가/고수익)': df[(df['pbr'] < pbr_median) & (df['roe'] > roe_median)],
        '2사분면 (Premium Area: 고평가/고수익)': df[(df['pbr'] > pbr_median) & (df['roe'] > roe_median)],
        '3사분면 (Value Trap: 저평가/저수익)': df[(df['pbr'] < pbr_median) & (df['roe'] < roe_median)],
        '4사분면 (Avoid Area: 고평가/저수익)': df[(df['pbr'] > pbr_median) & (df['roe'] < roe_median)]
    }
    
    print("| 포지션 (Quadrant) | 종목명 | 업종 | ROE | PBR | 1년 수익률 |")
    print("| :--- | :--- | :--- | :---: | :---: | :---: |")
    
    for quad_name, sub_df in quadrants.items():
        # 각 사분면에서 대표성을 띄는 종목 추출 (여기서는 시가총액/거래량 데이터가 없으므로 해당 집단의 극단이 아닌 안정권 무작위 3개 추출)
        # 안정성을 위해 해당 사분면 수익률 상/하위 10% 제외 후 샘플링
        q_low = sub_df['return_1yr'].quantile(0.1)
        q_high = sub_df['return_1yr'].quantile(0.9)
        safe_df = sub_df[(sub_df['return_1yr'] > q_low) & (sub_df['return_1yr'] < q_high)]
        
        sample = safe_df.sample(n=3, random_state=42)
        
        for idx, row in sample.iterrows():
            roe_str = f"{row['roe']:.1f}%"
            pbr_str = f"{row['pbr']:.2f}배"
            ret_str = f"{row['return_1yr']:.2f}%"
            print(f"| **{quad_name}** | {row['stock_name']} | {row['wics_name']} | {roe_str} | {pbr_str} | **{ret_str}** |")

if __name__ == "__main__":
    extract_quadrant_samples()
