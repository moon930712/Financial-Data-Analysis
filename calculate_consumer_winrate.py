import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("Loading raw data...")
    # Load the raw events data from previous run
    df_raw = pd.read_excel('pattern_robustness_analysis.xlsx', sheet_name='Raw Data')
    
    # Calculate D+5 Win Rate for each pattern
    results = []
    
    for pattern, group in df_raw.groupby('Pattern'):
        total_count = len(group)
        if total_count < 100:
            continue
            
        # Count how many times the unfiltered D+5 return was strictly positive (> 0)
        win_d5_count = len(group[group['Unfiltered D+5 Return (%)'] > 0])
        win_d5_rate = (win_d5_count / total_count) * 100
        
        avg_d5_return = group['Unfiltered D+5 Return (%)'].mean()
        avg_max_return = group['Max 5-Day Return (%)'].mean()
        avg_min_return = group['Min 5-Day Return (%)'].mean()
        
        results.append({
            'Pattern': pattern,
            'Total Count': total_count,
            'D+5 Win Count (>0%)': win_d5_count,
            'D+5 Win Rate (%)': round(win_d5_rate, 2),
            'Avg D+5 Return (%)': round(avg_d5_return, 2),
            'Avg Max Return (%)': round(avg_max_return, 2),
            'Avg Min Return (%)': round(avg_min_return, 2)
        })
        
    df_results = pd.DataFrame(results)
    
    # Sort by D+5 Win Rate (Descending), then Avg D+5 Return (Descending)
    df_results = df_results.sort_values(by=['D+5 Win Rate (%)', 'Avg D+5 Return (%)'], ascending=[False, False])
    
    excel_path = 'consumer_winrate_ranking.xlsx'
    df_results.to_excel(excel_path, index=False)
    
    print(f"\n=== Top 10 Patterns by D+5 Hold-to-Maturity Win Rate ===")
    print(df_results.head(10).to_string(index=False))
    print(f"\nSaved full results to {excel_path}")

if __name__ == '__main__':
    main()
