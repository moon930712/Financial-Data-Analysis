import os
import psycopg2
import pandas as pd
import numpy as np
import warnings
from itertools import product

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

def run_analysis():
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # 테마별 글로벌 랭킹 데이터 가져오기
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
    ORDER BY theme_name ASC, date ASC
    """
    
    print("Fetching ranks...")
    df_ranks = pd.read_sql(query_ranks, conn)
    df_ranks['date'] = pd.to_datetime(df_ranks['date'])
    df_ranks = df_ranks.sort_values(['theme_name', 'date']).reset_index(drop=True)
    
    # 과거 2일 랭킹 컬럼 추가 (D-2, D-1, D-day)
    df_ranks['rank_t_1'] = df_ranks.groupby('theme_name')['global_rank'].shift(1)
    df_ranks['rank_t_2'] = df_ranks.groupby('theme_name')['global_rank'].shift(2)
    df_ranks.dropna(subset=['rank_t_1', 'rank_t_2'], inplace=True)
    
    # 거래일 리스트 구축
    valid_dates_query = "SELECT DISTINCT date FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2025-01-02' ORDER BY date"
    df_dates = pd.read_sql(valid_dates_query, conn)
    date_list = df_dates['date'].astype(str).tolist()
    
    next_5_days = {}
    for i, d in enumerate(date_list):
        next_5_days[d] = date_list[i+1:i+6]
        
    # 모든 종가 데이터를 메모리에 적재하여 처리 속도 극대화
    q_all_prices = """
    SELECT v.date, v.stock_code, v.close, nt.theme_name
    FROM visual.vsl_anly_stocks_price_subindex01 v
    INNER JOIN industry.theme_name_list nt ON v.stock_code = nt.stock_code
    WHERE v.date >= '2025-01-02'
    """
    print("Loading all prices into memory...")
    df_prices = pd.read_sql(q_all_prices, conn)
    df_prices['date'] = df_prices['date'].astype(str)
    
    df_prices_unique = df_prices[['date', 'stock_code', 'close']].drop_duplicates()
    pt_close = df_prices_unique.pivot(index='date', columns='stock_code', values='close')
    
    theme_stocks = df_prices.groupby('theme_name')['stock_code'].unique().to_dict()
    
    print("Calculating daily returns for all events...")
    raw_results = []
    
    for idx, row in df_ranks.iterrows():
        dt = row['date'].strftime('%Y-%m-%d')
        theme = row['theme_name']
        
        future_dts = next_5_days.get(dt, [])
        if len(future_dts) < 5:
            # D+5일 데이터가 완성되지 않은 최근 시그널은 제외
            continue
            
        stocks = theme_stocks.get(theme, [])
        if len(stocks) == 0:
            continue
            
        try:
            entry_prices = pt_close.loc[dt, stocks]
            valid_stocks = entry_prices.dropna().index
            if len(valid_stocks) == 0:
                continue
                
            entry_prices = entry_prices[valid_stocks]
            daily_returns = []
            
            for f_dt in future_dts:
                if f_dt not in pt_close.index:
                    daily_returns.append(None)
                    continue
                future_prices = pt_close.loc[f_dt, valid_stocks]
                
                valid_mask = future_prices.notna() & (entry_prices > 0)
                if not valid_mask.any():
                    daily_returns.append(None)
                    continue
                
                ret = ((future_prices[valid_mask] - entry_prices[valid_mask]) / entry_prices[valid_mask]).mean() * 100
                daily_returns.append(round(ret, 4))
                
            # D+5일 수익률이 확실히 존재하는 경우만 포함
            if len(daily_returns) == 5 and all(r is not None for r in daily_returns):
                ranks = [row['rank_t_2'], row['rank_t_1'], row['global_rank']]
                labels = [get_rank_label(r) for r in ranks]
                pattern_str = " -> ".join(labels)
                
                raw_results.append({
                    'Date': dt,
                    'Theme Name': theme,
                    'Pattern': pattern_str,
                    'Ranks': f"[{int(ranks[0])}, {int(ranks[1])}, {int(ranks[2])}]",
                    'D+1 Return (%)': daily_returns[0],
                    'D+2 Return (%)': daily_returns[1],
                    'D+3 Return (%)': daily_returns[2],
                    'D+4 Return (%)': daily_returns[3],
                    'D+5 Return (%)': daily_returns[4]
                })
        except KeyError:
            continue

    df_raw = pd.DataFrame(raw_results)
    print(f"Total raw events generated: {len(df_raw)}")
    
    # 216개 모든 패턴 조합 생성 (6개 등급)
    labels = ['1등급', '2등급', '3등급', '4등급', '5등급', '6등급']
    all_possible = [" -> ".join(p) for p in product(labels, repeat=3)]
    df_all_patterns = pd.DataFrame({'Pattern': all_possible})
    
    # 패턴 통계 산출
    if not df_raw.empty:
        stats_list = []
        for pattern, group in df_raw.groupby('Pattern'):
            total_cnt = len(group)
            win_d5_cnt = len(group[group['D+5 Return (%)'] > 0])
            win_rate = (win_d5_cnt / total_cnt) * 100
            
            stats_list.append({
                'Pattern': pattern,
                'Count': total_cnt,
                'D+5 Win Rate (%)': round(win_rate, 2),
                'D+5 Return (Median)': round(group['D+5 Return (%)'].median(), 2),
                'D+5 Return (Average)': round(group['D+5 Return (%)'].mean(), 2),
                'D+1 Median': round(group['D+1 Return (%)'].median(), 2),
                'D+2 Median': round(group['D+2 Return (%)'].median(), 2),
                'D+3 Median': round(group['D+3 Return (%)'].median(), 2),
                'D+4 Median': round(group['D+4 Return (%)'].median(), 2)
            })
        
        df_stats_calc = pd.DataFrame(stats_list)
        
        # 343개 모든 패턴과 머지하여 빈도수가 0인 경우도 포함
        df_final_stats = pd.merge(df_all_patterns, df_stats_calc, on='Pattern', how='left')
        df_final_stats['Count'] = df_final_stats['Count'].fillna(0).astype(int)
        df_final_stats['D+5 Win Rate (%)'] = df_final_stats['D+5 Win Rate (%)'].fillna(0.0)
        
        # Count >= 100 필터링 적용 (변별력 없는 패턴 제거)
        df_final_stats = df_final_stats[df_final_stats['Count'] >= 100]
        
        # 임시 왜도(양의 왜수) 컬럼 생성 (Average >= Median 여부)
        df_final_stats['Is_Skewed_Positive'] = (df_final_stats['D+5 Return (Average)'] >= df_final_stats['D+5 Return (Median)']).astype(int)
        
        # 다중 정렬 규칙 적용: Win Rate (내림차순) -> Median Return (내림차순) -> Skewed Positive (내림차순) -> Count (내림차순)
        df_final_stats = df_final_stats.sort_values(
            by=['D+5 Win Rate (%)', 'D+5 Return (Median)', 'Is_Skewed_Positive', 'Count'], 
            ascending=[False, False, False, False]
        ).reset_index(drop=True)
        
        # 임시 컬럼 제거
        df_final_stats.drop(columns=['Is_Skewed_Positive'], inplace=True)
    else:
        df_final_stats = df_all_patterns.copy()
        for col in ['Count', 'D+5 Win Rate (%)', 'D+5 Return (Median)', 'D+5 Return (Average)', 'D+1 Median', 'D+2 Median', 'D+3 Median', 'D+4 Median']:
            df_final_stats[col] = np.nan

            
    # 엑셀 저장
    excel_path = 'pattern_consumer_stats_master.xlsx'
    with pd.ExcelWriter(excel_path) as writer:
        df_final_stats.to_excel(writer, sheet_name='Pattern Stats', index=False)
        df_raw.to_excel(writer, sheet_name='Raw Data', index=False)
        
    print(f"Master pattern statistics saved to {excel_path}")
    conn.close()

if __name__ == "__main__":
    run_analysis()
