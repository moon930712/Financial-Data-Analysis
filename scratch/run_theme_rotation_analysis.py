import psycopg2, os
import pandas as pd
import sys
import io
# Set encoding to utf-8 for console output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
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
        host=os.environ.get('DB_HOST')
        , port=os.environ.get('DB_PORT', 5432)
        , dbname=os.environ.get('DB_NAME')
        , user=os.environ.get('DB_USER')
        , password=os.environ.get('DB_PASSWORD')
    )
# 통합 순환매 마스터 SQL 실행
with open('src/sql/industry_rotation_master.sql', 'r', encoding='utf-8') as f:
    sql_master = f.read()
try:
    conn = get_connection()
    df_result = pd.read_sql(sql_master, conn)
    print("\n" + "="*80)
    print("### [표준화 및 시총 가중치 기반 업종 순환매 분석 결과] ###")
    print("="*80)
    if not df_result.empty:
        # SQL에서 변경된 컬럼명 반영 (바닥신호 -> MACD음수맥스 등)
        # 현재 SQL에서 일부 컬럼이 주석처리되어 있을 수 있으므로 존재하는 컬럼만 선택
        available_cols = df_result.columns.tolist()
        display_cols = [c for c in ['날짜', '순위', '업종명', '전체종목수', '로테이션스코어', '국면진단'] if c in available_cols]
        print(df_result[display_cols].head(30).to_string(index=False))
        print("\n" + "-"*80)
        print("※ 전체종목수는 '4개 신호 중 하나라도 발생한 종목 수'를 의미합니다 (최소 3개 필터링 적용).")
        print("※ 로테이션스코어는 종목 개수가 아닌 '시가총액 영향력'을 기반으로 산출되었습니다.")
        print("="*80)
    else:
        print("현재 신호 발생 종목이 3개 이상인 업종이 없습니다.")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
