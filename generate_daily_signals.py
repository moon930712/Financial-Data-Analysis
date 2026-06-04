import os
import sys
import psycopg2
import pandas as pd
import numpy as np
import warnings
from datetime import datetime

warnings.filterwarnings('ignore', category=UserWarning)

def load_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env_vars[k] = v
    except: pass
    return env_vars

env = load_env()

def get_rank_label(rank):
    if pd.isna(rank):
        return None
    if rank <= 25:
        return '1등급'
    elif rank <= 50:
        return '2등급'
    elif rank <= 75:
        return '3등급'
    elif rank <= 100:
        return '4등급'
    elif rank <= 125:
        return '5등급'
    else:
        return '6등급'

def get_daily_signals(target_date=None):
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # target_date가 지정되지 않은 경우 가장 최신 날짜 가져오기
    if not target_date:
        q_latest = "SELECT MAX(date) as max_date FROM visual.vsl_anly_stocks_price_subindex01"
        df_latest = pd.read_sql(q_latest, conn)
        if not df_latest.empty and df_latest['max_date'].iloc[0] is not None:
            target_date = df_latest['max_date'].iloc[0].strftime('%Y-%m-%d')
        else:
            target_date = '2026-03-18' # 폴백 디폴트
            
    print(f"Target Date: {target_date}")
    
    # target_date를 포함하여 직전 5거래일 리스트 가져오기 (shift 연산을 위해 충분한 날짜 확보)
    q_dates = f"""
    SELECT DISTINCT date 
    FROM visual.vsl_anly_stocks_price_subindex01 
    WHERE date <= '{target_date}'::date 
    ORDER BY date DESC 
    LIMIT 10
    """
    df_dates = pd.read_sql(q_dates, conn)
    past_dates = df_dates['date'].astype(str).tolist()
    
    if not past_dates:
        print(f"No date history found for {target_date}")
        conn.close()
        return
        
    dates_str = "'" + "','".join(past_dates) + "'"
    
    # 랭킹 쿼리
    query_ranks = f"""
    WITH histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= (SELECT MIN(date) FROM visual.vsl_anly_stocks_price_subindex01 WHERE date <= '{target_date}'::date) - INTERVAL '30 days'
          AND m.date <= '{target_date}'::date
    )
    , phase_calc AS (
        SELECT date, stock_code, stock_name
            , CASE 
                WHEN histogram < 0 AND histogram > lag_histogram THEN 1
                WHEN histogram < 0 AND histogram <= lag_histogram THEN 2
                WHEN histogram >= 0 AND histogram > lag_histogram THEN 3
                WHEN histogram >= 0 AND histogram <= lag_histogram THEN 4
                ELSE 4
            END AS phase
        FROM histo_base
        WHERE date IN ({dates_str})
    )
    , theme_aggregation AS (
        SELECT nt.theme_name, p.date
            , COUNT(*) AS total_cnt
            , SUM(CASE WHEN p.phase = 1 THEN 1 ELSE 0 END) AS phase1_cnt
            , SUM(CASE WHEN p.phase = 2 THEN 1 ELSE 0 END) AS phase2_cnt
            , SUM(CASE WHEN p.phase = 3 THEN 1 ELSE 0 END) AS phase3_cnt
            , SUM(CASE WHEN p.phase = 4 THEN 1 ELSE 0 END) AS phase4_cnt
            , COALESCE(SUM(v1.trade_value), 0) / COUNT(*) AS avg_trade_value
        FROM industry.theme_name_list nt 
        INNER JOIN phase_calc p ON nt.stock_code = p.stock_code
        LEFT JOIN visual.vsl_anly_stocks_price_subindex01 v1 ON p.stock_code = v1.stock_code AND p.date = v1.date
        WHERE v1.close > 1000 
        GROUP BY nt.theme_name, p.date
        HAVING COUNT(*) >= 5 
    )
    , trade_rank_calc AS (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY date ORDER BY avg_trade_value DESC NULLS LAST) AS trade_value_rank
        FROM theme_aggregation
    )
    , final_ranking AS (
        SELECT date, theme_name
            , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                total_cnt DESC
              ) AS global_rank
        FROM trade_rank_calc
        WHERE trade_value_rank <= 150
    )
    SELECT date, theme_name, global_rank
    FROM final_ranking
    ORDER BY theme_name ASC, date ASC
    """
    
    df_ranks = pd.read_sql(query_ranks, conn)
    df_ranks['date'] = df_ranks['date'].astype(str)
    
    # target_date 당일 데이터 필터링
    df_today = df_ranks[df_ranks['date'] == target_date].copy()
    if df_today.empty:
        print(f"No rank data found for target date: {target_date}")
        conn.close()
        return
        
    # 과거 2거래일의 날짜 구하기
    sorted_past_dates = sorted(past_dates) # 과거 순서대로 정렬
    target_idx = sorted_past_dates.index(target_date)
    if target_idx < 2:
        print("Not enough history to compute 3-day pattern.")
        conn.close()
        return
        
    d_minus_1 = sorted_past_dates[target_idx - 1]
    d_minus_2 = sorted_past_dates[target_idx - 2]
    
    results = []
    
    # 당일 상위 20위 테마에 대해 3일 패턴 추출
    df_today_top = df_today[df_today['global_rank'] <= 20].sort_values('global_rank')
    
    for idx, row in df_today_top.iterrows():
        theme = row['theme_name']
        rank_today = row['global_rank']
        
        # D-1 랭킹 조회
        row_minus_1 = df_ranks[(df_ranks['theme_name'] == theme) & (df_ranks['date'] == d_minus_1)]
        rank_minus_1 = row_minus_1['global_rank'].iloc[0] if not row_minus_1.empty else np.nan
        
        # D-2 랭킹 조회
        row_minus_2 = df_ranks[(df_ranks['theme_name'] == theme) & (df_ranks['date'] == d_minus_2)]
        rank_minus_2 = row_minus_2['global_rank'].iloc[0] if not row_minus_2.empty else np.nan
        
        if not pd.isna(rank_minus_1) and not pd.isna(rank_minus_2):
            ranks = [rank_minus_2, rank_minus_1, rank_today]
            labels = [get_rank_label(r) for r in ranks]
            pattern_str = " -> ".join(labels)
            
            results.append({
                'Theme Name': theme,
                'Rank(D-day)': int(rank_today),
                'Rank(D-1)': int(rank_minus_1),
                'Rank(D-2)': int(rank_minus_2),
                'Pattern': pattern_str
            })
            
    df_signals = pd.DataFrame(results)
    
    if df_signals.empty:
        print("No valid 3-day patterns generated for today's top themes.")
        conn.close()
        return
        
    # 마스터 통계 데이터 읽기
    master_path = 'pattern_consumer_stats_master.xlsx'
    if not os.path.exists(master_path):
        print(f"Error: {master_path} does not exist. Run calculate_all_patterns_stats.py first.")
        conn.close()
        return
        
    df_master = pd.read_excel(master_path, sheet_name='Pattern Stats')
    
    # 시그널 테마와 과거 D+5 통계 매핑 (Left Join)
    df_merged = pd.merge(df_signals, df_master, on='Pattern', how='left')
    
    # Count >= 100 필터링 적용 (표본 수가 100개 이상인 패턴만 추천 대상으로 한정)
    df_merged = df_merged[df_merged['Count'] >= 100]
    
    if not df_merged.empty:
        # 임시 왜도(양의 왜수) 컬럼 생성
        df_merged['Is_Skewed_Positive'] = (df_merged['D+5 Return (Average)'] >= df_merged['D+5 Return (Median)']).astype(int)
        
        # 다중 정렬 규칙 적용: Win Rate (내림차순) -> Median Return (내림차순) -> Is_Skewed_Positive (내림차순) -> Count (내림차순)
        df_merged = df_merged.sort_values(
            by=['D+5 Win Rate (%)', 'D+5 Return (Median)', 'Is_Skewed_Positive', 'Count'], 
            ascending=[False, False, False, False]
        ).reset_index(drop=True)
        
        # 임시 컬럼 제거
        df_merged.drop(columns=['Is_Skewed_Positive'], inplace=True)
    else:
        df_merged = pd.DataFrame()

    
    # 저장 폴더 생성 및 엑셀 저장
    os.makedirs('result', exist_ok=True)
    output_path = f'result/daily_signals_{target_date}.xlsx'
    df_merged.to_excel(output_path, index=False)
    
    print(f"\n=== Daily Theme Signals with Past Stats ({target_date}) ===")
    print(df_merged.to_string(index=False))
    print(f"\nSaved daily recommendation signals to {output_path}")
    
    conn.close()
    return df_merged

if __name__ == "__main__":
    t_date = sys.argv[1] if len(sys.argv) > 1 else None
    get_daily_signals(t_date)
