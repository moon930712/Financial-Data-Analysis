import os, psycopg2, pandas as pd

[os.environ.setdefault(k,v) for line in open('.env') if '=' in line for k,v in [line.strip().split('=',1)]]
conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', 5432), dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])

pd.set_option('display.max_columns', None)

# 1. vsl_anly_stocks_price_subindex01 순매수 컬럼 확인
# 1. KOSPI/KOSDAQ 종목 정보 테이블 컬럼 확인
for table in ['kis_kospi_info', 'kis_kosdaq_info']:
    q = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}';"
    print(f"\n{table} columns:")
    print(pd.read_sql_query(q, conn))
    
    # 샘플 데이터 확인 (발행주식수 추정 컬럼)
    q_sample = f"SELECT shortcode, name, listed_shares FROM company.{table} LIMIT 3;"
    try:
        print(f"\n{table} sample (listed_shares):")
        print(pd.read_sql_query(q_sample, conn))
    except Exception as e:
        print(f"Column 'listed_shares' not found in {table}, trying general sample...")
        print(pd.read_sql_query(f"SELECT * FROM company.{table} LIMIT 1;", conn))

# 2. 투자자별 순매수량 데이터 샘플 확인 (정확한 값 단위 확인)
q_investor = "SELECT * FROM company.krx_stocks_investor_shares_trading_info WHERE investor IN ('외국인', '기관합계') LIMIT 5;"
print("\nInvestor trading info sample:")
print(pd.read_sql_query(q_investor, conn))

conn.close()
