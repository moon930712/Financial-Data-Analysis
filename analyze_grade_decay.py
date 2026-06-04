import os
import psycopg2
import pandas as pd
import numpy as np
import warnings

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

def get_grade_num(label):
    grade_map = {
        '1등급': 1.0,
        '2등급': 2.0,
        '3등급': 3.0,
        '4등급': 4.0,
        '5등급': 5.0,
        '6등급': 6.0
    }
    return grade_map.get(label, np.nan)

def run_grade_decay_analysis():
    master_path = 'pattern_consumer_stats_master.xlsx'
    if not os.path.exists(master_path):
        print(f"Error: {master_path} does not exist. Run calculate_all_patterns_stats.py first.")
        return
        
    print("Loading master statistics...")
    df_stats = pd.read_excel(master_path, sheet_name='Pattern Stats')
    df_raw = pd.read_excel(master_path, sheet_name='Raw Data')
    
    # 성과 상위 10개 패턴 선정 (소비자 관점 랭킹 순서 유지)
    top_10_patterns = df_stats.head(10)['Pattern'].tolist()
    print(f"Top 10 Patterns selected:\n {top_10_patterns}")
    
    # 상위 10개 패턴에 해당하는 raw 이벤트만 필터링
    df_target_events = df_raw[df_raw['Pattern'].isin(top_10_patterns)].copy()
    
    # 데이터베이스 연동하여 랭킹 매핑 테이블 구축
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # 전체 기간 랭킹 쿼리 (속도 극대화를 위해 메모리 적재)
    query_ranks = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2025-01-02' AND date <= '2026-05-15'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code, m.stock_name
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2024-12-01' AND m.date <= '2026-05-15'
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
        WHERE date IN (SELECT date FROM valid_dates)
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
    """
    
    print("Fetching ranks from DB for grade matching...")
    df_ranks = pd.read_sql(query_ranks, conn)
    df_ranks['date'] = df_ranks['date'].astype(str)
    
    rank_cache = {}
    for idx, row in df_ranks.iterrows():
        rank_cache[(row['theme_name'], row['date'])] = row['global_rank']
        
    valid_dates_query = "SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2025-01-02' ORDER BY date"
    df_dates = pd.read_sql(valid_dates_query, conn)
    date_list = df_dates['date'].astype(str).tolist()
    
    next_5_days = {}
    for i, d in enumerate(date_list):
        next_5_days[d] = date_list[i+1:i+6]
        
    print("Tracking future grades and returns (D+1 to D+5)...")
    decay_events = []
    
    for idx, row in df_target_events.iterrows():
        dt = str(row['Date'])
        theme = row['Theme Name']
        pattern = row['Pattern']
        
        future_dts = next_5_days.get(dt, [])
        if len(future_dts) < 5:
            continue
            
        future_grades = []
        future_grade_nums = []
        
        for f_dt in future_dts:
            rank = rank_cache.get((theme, f_dt), np.nan)
            label = get_rank_label(rank)
            num = get_grade_num(label)
            
            future_grades.append(label if label else '6등급')
            future_grade_nums.append(num if not pd.isna(num) else 6.0)
            
        decay_events.append({
            'Pattern': pattern,
            'Theme Name': theme,
            'Date': dt,
            'D+1 Grade': future_grades[0],
            'D+2 Grade': future_grades[1],
            'D+3 Grade': future_grades[2],
            'D+4 Grade': future_grades[3],
            'D+5 Grade': future_grades[4],
            'D+1 Num': future_grade_nums[0],
            'D+2 Num': future_grade_nums[1],
            'D+3 Num': future_grade_nums[2],
            'D+4 Num': future_grade_nums[3],
            'D+5 Num': future_grade_nums[4],
            'D+1 Return': row['D+1 Return (%)'],
            'D+2 Return': row['D+2 Return (%)'],
            'D+3 Return': row['D+3 Return (%)'],
            'D+4 Return': row['D+4 Return (%)'],
            'D+5 Return': row['D+5 Return (%)']
        })
        
    df_decay = pd.DataFrame(decay_events)
    
    print("Aggregating results...")
    
    # ① Summary 시트: 평균 및 중앙값 등급 연산 및 리스크 지표(변동성, 최대/최소, 손실확률) 추가
    summary_list = []
    for pattern in top_10_patterns:
        df_p = df_decay[df_decay['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        ret_d5 = df_p['D+5 Return']
        
        summary_list.append({
            'Pattern': pattern,
            'Count': len(df_p),
            'D+1 Avg Grade': round(df_p['D+1 Num'].mean(), 2),
            'D+1 Med Grade': round(df_p['D+1 Num'].median(), 1),
            'D+2 Avg Grade': round(df_p['D+2 Num'].mean(), 2),
            'D+2 Med Grade': round(df_p['D+2 Num'].median(), 1),
            'D+3 Avg Grade': round(df_p['D+3 Num'].mean(), 2),
            'D+3 Med Grade': round(df_p['D+3 Num'].median(), 1),
            'D+4 Avg Grade': round(df_p['D+4 Num'].mean(), 2),
            'D+4 Med Grade': round(df_p['D+4 Num'].median(), 1),
            'D+5 Avg Grade': round(df_p['D+5 Num'].mean(), 2),
            'D+5 Med Grade': round(df_p['D+5 Num'].median(), 1),
            'Std Dev (%)': round(ret_d5.std(), 2) if len(ret_d5) > 1 else 0.0,
            'Max Return (%)': round(ret_d5.max(), 2) if not ret_d5.empty else 0.0,
            'Min Return (%)': round(ret_d5.min(), 2) if not ret_d5.empty else 0.0,
            'Risk Ratio (<= -5%) (%)': round((ret_d5 <= -5.0).mean() * 100, 2) if not ret_d5.empty else 0.0,
        })
    df_summary = pd.DataFrame(summary_list)
    
    # ② Distribution 시트: 가로형 피벗 구성 (각 등급별 비중과 수익률을 한 행에 나열)
    dist_list = []
    grades_labels = ['1등급', '2등급', '3등급', '4등급', '5등급', '6등급']
    
    for pattern in top_10_patterns:
        df_p = df_decay[df_decay['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        total_p_cnt = len(df_p)
        
        for day_idx in range(1, 6):
            grade_col = f'D+{day_idx} Grade'
            return_col = f'D+{day_idx} Return'
            
            row_data = {
                'Pattern': pattern,
                'Day': f'D+{day_idx}'
            }
            
            for g in grades_labels:
                df_g = df_p[df_p[grade_col] == g]
                g_cnt = len(df_g)
                ratio = round((g_cnt / total_p_cnt) * 100, 2) if total_p_cnt > 0 else 0.0
                avg_ret = round(df_g[return_col].mean(), 2) if g_cnt > 0 else 0.0
                med_ret = round(df_g[return_col].median(), 2) if g_cnt > 0 else 0.0
                
                row_data[f'{g} 비중 (%)'] = ratio
                row_data[f'{g} 평균수익률 (%)'] = avg_ret
                row_data[f'{g} 중앙값수익률 (%)'] = med_ret
                
            dist_list.append(row_data)
            
    df_dist = pd.DataFrame(dist_list)
    
    # ③ Theme Distribution 시트: 패턴별 다빈도 테마 분포 집계
    theme_dist_list = []
    for pattern in top_10_patterns:
        df_p = df_decay[df_decay['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        total_p_cnt = len(df_p)
        theme_counts = df_p['Theme Name'].value_counts()
        
        for rank_idx, (theme, count) in enumerate(theme_counts.head(10).items(), 1):
            theme_dist_list.append({
                'Pattern': pattern,
                'Rank': rank_idx,
                'Theme Name': theme,
                'Occurrence Count': count,
                'Ratio (%)': round((count / total_p_cnt) * 100, 2)
            })
            
    df_theme_dist = pd.DataFrame(theme_dist_list)
    
    # ④ Optimal Path 시트: 진입 후 D+1~D+5 등급 경로별 성과 랭킹화
    path_list = []
    # 등급 경로 칼럼 생성
    df_decay['Path'] = df_decay['D+1 Grade'] + ' -> ' + df_decay['D+2 Grade'] + ' -> ' + df_decay['D+3 Grade'] + ' -> ' + df_decay['D+4 Grade'] + ' -> ' + df_decay['D+5 Grade']
    
    for pattern in top_10_patterns:
        df_p = df_decay[df_decay['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        total_p_cnt = len(df_p)
        pat_paths = []
        
        # 경로별 그룹바이 집계
        for path_str, group in df_p.groupby('Path'):
            path_cnt = len(group)
            
            # 신뢰성을 위해 Count >= 3 이상인 유의미한 등급 이동 경로만 수집 (노이즈 방지)
            if path_cnt >= 3:
                pat_paths.append({
                    'Pattern': pattern,
                    'D+1 ~ D+5 Grade Path': path_str,
                    'Count': path_cnt,
                    'Ratio (%)': round((path_cnt / total_p_cnt) * 100, 2),
                    'D+5 Return (Average) (%)': round(group['D+5 Return'].mean(), 2),
                    'D+5 Return (Median) (%)': round(group['D+5 Return'].median(), 2)
                })
                
        # 각 패턴별로 D+5 Return (Median) 내림차순 정렬 및 Rank 부여
        if pat_paths:
            df_pat_path = pd.DataFrame(pat_paths)
            df_pat_path = df_pat_path.sort_values(by=['D+5 Return (Median) (%)', 'Count'], ascending=[False, False]).reset_index(drop=True)
            df_pat_path.insert(1, 'Rank', range(1, len(df_pat_path) + 1))
            path_list.append(df_pat_path)
            
    if path_list:
        df_path_analysis = pd.concat(path_list, ignore_index=True)
    else:
        df_path_analysis = pd.DataFrame()
    
    # ⑤ Return Stats 시트: 패턴별 일자별 단순 수익률 평균 및 중앙값
    return_stats_list = []
    for pattern in top_10_patterns:
        df_p = df_raw[df_raw['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        for day_idx in range(1, 6):
            col = f'D+{day_idx} Return (%)'
            return_stats_list.append({
                'Pattern': pattern,
                'Day': f'D+{day_idx}',
                'Return (Average) (%)': round(df_p[col].mean(), 2),
                'Return (Median) (%)': round(df_p[col].median(), 2)
            })
            
    df_return_stats = pd.DataFrame(return_stats_list)
    
    # 엑셀 저장
    output_excel = 'pattern_grade_transition_v2.xlsx'
    with pd.ExcelWriter(output_excel) as writer:
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        df_dist.to_excel(writer, sheet_name='Distribution', index=False)
        df_path_analysis.to_excel(writer, sheet_name='Optimal Path', index=False)
        df_theme_dist.to_excel(writer, sheet_name='Theme Distribution', index=False)
        df_return_stats.to_excel(writer, sheet_name='Return Stats', index=False)
        
    print(f"Decay analysis, distribution, path analysis, and return stats saved to {output_excel}")
    conn.close()

if __name__ == "__main__":
    run_grade_decay_analysis()
