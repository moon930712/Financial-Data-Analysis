import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    # Load the data
    df = pd.read_excel('pattern_robustness_analysis.xlsx', sheet_name='Robustness Summary')

    # 1. Total Count >= 100
    df = df[df['Total Count'] >= 100].copy()

    # 2. Win Rate > Loss Rate
    df = df[df['Win Rate (%)'] > df['Loss Rate (%)']]

    # 3. Calculate Win Margin
    df['Win Margin (%)'] = df['Win Rate (%)'] - df['Loss Rate (%)']

    # 4. Sort
    df = df.sort_values(by=['Win Margin (%)', 'Avg D+5 Return (%)', 'Avg Min Return (%)'], ascending=[False, False, False])

    # Select columns
    cols = ['Pattern', 'Total Count', 'Win Margin (%)', 'Win Rate (%)', 'Loss Rate (%)', 'Avg D+5 Return (%)', 'Avg Max Return (%)', 'Avg Min Return (%)']
    df = df[cols]

    # Save to Excel
    df.to_excel('best_patterns_ranking.xlsx', index=False)

    print("=== Top 10 Best Trading Patterns ===")
    print(df.head(10).to_string(index=False))

if __name__ == '__main__':
    main()
