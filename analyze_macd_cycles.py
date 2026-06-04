import os
import psycopg2
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def load_env(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

def get_connection():
    load_env('.env')
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', 5432),
        dbname=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD')
    )

def run_analysis():
    conn = get_connection()
    try:
        # 1. SQL 파일에서 쿼리 읽기
        sql_path = os.path.join('src', 'sql', 'macd_cycle_analysis.sql')
        with open(sql_path, 'r', encoding='utf-8') as f:
            query = f.read()
        
        print("MACD 사이클 데이터 추출 중...")
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("데이터가 없습니다.")
            return

        # 2. 통계 분석
        print("\n[ 업종별(중분류) MACD 사이클 통계 요약 ]")
        
        # 상승구간과 하락구간 분리
        up_df = df[df['구간구분'] == '상승구간(0선위)']
        down_df = df[df['구간구분'] == '하락구간(0선밑)']
        
        # 중분류별 평균 지속일수 계산
        stats = df.groupby(['중분류', '구간구분'])['지속일수'].agg(['mean', 'median', 'std', 'count']).reset_index()
        
        # 피벗 테이블로 보기 좋게 변환
        pivot_stats = stats.pivot(index='중분류', columns='구간구분', values='mean')
        pivot_stats = pivot_stats.sort_values(by='상승구간(0선위)', ascending=False)
        
        print(pivot_stats.head(20))
        pivot_stats.to_csv('result/macd_cycle_stats.csv', encoding='utf-8-sig')
        print(f"\n통계 데이터 저장 완료: result/macd_cycle_stats.csv")
        
        # 3. 시각화 (상위 10개 업종)
        plt.figure(figsize=(15, 8))
        top_10_sectors = pivot_stats.head(10).index
        plot_df = df[df['중분류'].isin(top_10_sectors)]
        
        sns.boxplot(x='중분류', y='지속일수', hue='구간구분', data=plot_df)
        plt.title('상위 10개 업종별 MACD 히스토그램 사이클 지속 일수 (Boxplot)', fontsize=15)
        plt.xticks(rotation=45)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        os.makedirs('result', exist_ok=True)
        plt.savefig('result/macd_cycle_analysis.png', bbox_inches='tight')
        print(f"\n시각화 결과 저장 완료: result/macd_cycle_analysis.png")
        
        # 4. 전체 평균
        total_avg_up = up_df['지속일수'].mean()
        total_avg_down = down_df['지속일수'].mean()
        print(f"\n[ 전체 종목 평균 ]")
        print(f"평균 상승 지속일(0선 위): {total_avg_up:.2f}일")
        print(f"평균 하락 지속일(0선 밑): {total_avg_down:.2f}일")

    finally:
        conn.close()

if __name__ == "__main__":
    run_analysis()
