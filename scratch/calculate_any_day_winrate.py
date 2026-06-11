import pandas as pd
import numpy as np
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("Loading raw data from pattern_consumer_stats_master.xlsx...")
    df_raw = pd.read_excel('pattern_consumer_stats_master.xlsx', sheet_name='Raw Data')
    
    # Calculate Max Return over the 5 days
    return_cols = ['D+1 Return (%)', 'D+2 Return (%)', 'D+3 Return (%)', 'D+4 Return (%)', 'D+5 Return (%)']
    df_raw['Max 5-Day Return (%)'] = df_raw[return_cols].max(axis=1)
    
    stats_list = []
    for pattern, group in df_raw.groupby('Pattern'):
        total_cnt = len(group)
        if total_cnt < 100:
            continue
            
        win_any_day_cnt = len(group[group['Max 5-Day Return (%)'] > 0])
        win_rate = (win_any_day_cnt / total_cnt) * 100
        
        stats_list.append({
            'Pattern': pattern,
            'Count': total_cnt,
            'Any Day Win Rate (%)': round(win_rate, 2),
            'D+5 Return (Median)': round(group['D+5 Return (%)'].median(), 2),
            'D+5 Return (Average)': round(group['D+5 Return (%)'].mean(), 2),
            'D+1 Median': round(group['D+1 Return (%)'].median(), 2),
            'D+2 Median': round(group['D+2 Return (%)'].median(), 2),
            'D+3 Median': round(group['D+3 Return (%)'].median(), 2),
            'D+4 Median': round(group['D+4 Return (%)'].median(), 2)
        })

    df_stats = pd.DataFrame(stats_list)
    
    # Sort
    df_stats['Is_Skewed_Positive'] = (df_stats['D+5 Return (Average)'] >= df_stats['D+5 Return (Median)']).astype(int)
    df_stats = df_stats.sort_values(
        by=['Any Day Win Rate (%)', 'D+5 Return (Median)', 'Is_Skewed_Positive', 'Count'], 
        ascending=[False, False, False, False]
    ).reset_index(drop=True)
    df_stats.drop(columns=['Is_Skewed_Positive'], inplace=True)

    excel_path = 'pattern_any_day_winrate.xlsx'
    df_stats.to_excel(excel_path, index=False)
    
    print("\n=== Top 10 Patterns by Any Day Win Rate (5일 중 1일이라도 수익 구간 도달) ===")
    print(df_stats.head(10).to_string(index=False))
    print(f"\nSaved full results to {excel_path}")

if __name__ == '__main__':
    main()
