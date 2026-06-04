import os
import psycopg2
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

def load_env():
    env_vars = {}
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env_vars[k] = v
    except: pass
    return env_vars

def main():
    env = load_env()
    print("Connecting to DB...")
    conn = psycopg2.connect(
        host=env.get('DB_HOST', 'localhost'), port=env.get('DB_PORT', 15432),
        dbname=env.get('DB_NAME', 'postgres'), user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD', 'postgres')
    )
    
    # 0. 종목명 매핑 추출 (추가됨)
    print("Fetching Stock Names...")
    query_names = "SELECT DISTINCT stock_code, stock_name FROM visual.vsl_anly_stocks_price_subindex02"
    df_names = pd.read_sql(query_names, conn)
    name_dict = dict(zip(df_names['stock_code'], df_names['stock_name']))
    
    # 1. 테마 랭킹 및 국면(Phase) 추출
    print("Fetching Top 10 Theme Stocks and their Phases...")
    query = """
    WITH valid_dates AS (
        SELECT DISTINCT date 
        FROM visual.vsl_anly_stocks_price_subindex01 
        WHERE date >= '2026-01-01' AND date <= '2026-05-15'
    )
    , histo_base AS (
        SELECT m.date, m.stock_code
            , (m.macd - m.signal) AS histogram
            , LAG(m.macd - m.signal, 1) OVER(PARTITION BY m.stock_code ORDER BY m.date) AS lag_histogram
        FROM visual.vsl_anly_stocks_price_subindex02 m
        WHERE m.date >= '2025-12-01' AND m.date <= '2026-05-15'
    )
    , phase_calc AS (
        SELECT date, stock_code
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
        SELECT date, theme_name, global_rank
             , LAG(global_rank) OVER(PARTITION BY theme_name ORDER BY date) as prev_rank
        FROM (
            SELECT date, theme_name
                , ROW_NUMBER() OVER(PARTITION BY date ORDER BY 
                    ROUND(((phase1_cnt::numeric * 2 + phase3_cnt::numeric - phase2_cnt::numeric * 1.5 - phase4_cnt::numeric * 1.2) / total_cnt), 4) DESC, 
                    ROUND((phase1_cnt::numeric / total_cnt) * 100, 2) DESC, 
                    total_cnt DESC
                  ) AS global_rank
            FROM trade_rank_calc
            WHERE trade_value_rank <= 150
        ) ranked
    )
    SELECT DISTINCT f.date, f.theme_name, f.global_rank as theme_rank, f.prev_rank, nt.stock_code, p.phase
    FROM final_ranking f
    INNER JOIN industry.theme_name_list nt ON f.theme_name = nt.theme_name
    INNER JOIN phase_calc p ON nt.stock_code = p.stock_code AND f.date = p.date
    WHERE p.phase IN (1, 2, 3, 4) AND f.global_rank <= 10
    """
    df_stocks = pd.read_sql(query, conn)
    df_stocks['date'] = pd.to_datetime(df_stocks['date'])
    
    # 2. 주가 데이터 로드
    print("Fetching Daily Prices...")
    query_prices = "SELECT date, stock_code, close FROM visual.vsl_anly_stocks_price_subindex01 WHERE date >= '2026-01-01'"
    df_prices = pd.read_sql(query_prices, conn)
    df_prices['date'] = pd.to_datetime(df_prices['date'])
    
    conn.close()
    
    # 3. 수익률 계산 (5일, 8일, 14일)
    print("Calculating Returns...")
    all_dates = sorted(df_prices['date'].unique())
    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    df_prices.set_index(['date', 'stock_code'], inplace=True)
    
    results = []
    
    for base_date, group in df_stocks.groupby('date'):
        if base_date not in date_to_idx: continue
        base_idx = date_to_idx[base_date]
        
        target_idx_5 = base_idx + 5
        target_idx_8 = base_idx + 8
        target_idx_14 = base_idx + 14
        
        stocks = group['stock_code'].unique()
        
        try:
            bp = df_prices.loc[(base_date, stocks), 'close']
        except KeyError:
            continue
            
        def get_prices(t_idx):
            if t_idx < len(all_dates):
                try:
                    return df_prices.loc[(all_dates[t_idx], stocks), 'close']
                except KeyError:
                    return None
            return None
            
        tp_5 = get_prices(target_idx_5)
        tp_8 = get_prices(target_idx_8)
        tp_14 = get_prices(target_idx_14)
        
        for _, row in group.iterrows():
            sc = row['stock_code']
            sname = name_dict.get(sc, sc)  # 추가: 종목명 가져오기
            bp_val = bp.loc[(base_date, sc)] if (base_date, sc) in bp.index else np.nan
            
            def calc_ret(tp, t_date):
                if tp is not None and (t_date, sc) in tp.index and pd.notna(bp_val) and bp_val > 0:
                    return (tp.loc[(t_date, sc)] - bp_val) / bp_val * 100
                return np.nan
                
            r5 = calc_ret(tp_5, all_dates[target_idx_5]) if target_idx_5 < len(all_dates) else np.nan
            r8 = calc_ret(tp_8, all_dates[target_idx_8]) if target_idx_8 < len(all_dates) else np.nan
            r14 = calc_ret(tp_14, all_dates[target_idx_14]) if target_idx_14 < len(all_dates) else np.nan
            
            results.append({
                '매수일(Date)': base_date.strftime('%Y-%m-%d'),
                '테마명(Theme)': row['theme_name'],
                '전일 테마랭킹': row['prev_rank'],
                '당일 테마랭킹': row['theme_rank'],
                '종목코드(Code)': sc,
                '종목명(Name)': sname,  # 추가된 부분!
                '진입 국면(Phase)': row['phase'],
                '5일후 수익률(%)': r5,
                '8일후 수익률(%)': r8,
                '14일후 수익률(%)': r14
            })
            
    df_raw = pd.DataFrame(results)
    
    print("Writing to Excel...")
    output_file = '백테스팅_검증용_상세데이터_v3.xlsx'
    
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        df_raw.to_excel(writer, sheet_name='1. Raw Data(전체종목)', index=False)
        
        df_target = df_raw[(df_raw['진입 국면(Phase)'] == 2) & (df_raw['14일후 수익률(%)'].notna())]
        df_target = df_target.sort_values(by='14일후 수익률(%)', ascending=False)
        df_target.to_excel(writer, sheet_name='2. 2국면_14일_상세분석', index=False)
        
        summary_data = []
        for phase in [1, 2, 3, 4]:
            phase_df = df_raw[df_raw['진입 국면(Phase)'] == phase]
            for period in ['5일후', '8일후', '14일후']:
                col = f'{period} 수익률(%)'
                s = phase_df[col].dropna()
                if len(s) == 0: continue
                
                Q1 = s.quantile(0.25)
                Q3 = s.quantile(0.75)
                IQR = Q3 - Q1
                valid_s = s[(s >= Q1 - 1.5 * IQR) & (s <= Q3 + 1.5 * IQR)]
                
                summary_data.append({
                    '진입 국면': f'{phase}국면',
                    '보유 기간': period,
                    '평균 수익률(%)': valid_s.mean(),
                    '중앙값(%)': valid_s.median(),
                    '승률(%)': (valid_s > 0).mean() * 100,
                    '모수(Count)': len(valid_s)
                })
        
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='3. 통계요약_아웃라이어제거', index=False)

        # Sheet 4: 중하위(61~100) -> 최상위 진입
        df_jump = df_raw[(df_raw['전일 테마랭킹'] >= 61) & (df_raw['전일 테마랭킹'] <= 100) & (df_raw['당일 테마랭킹'] <= 10)]
        df_jump = df_jump.sort_values(by=['매수일(Date)', '14일후 수익률(%)'], ascending=[True, False])
        df_jump.to_excel(writer, sheet_name='4. Jump(중하위_to_최상위)', index=False)

    print(f"Done! Saved to {output_file}")

if __name__ == '__main__':
    main()
