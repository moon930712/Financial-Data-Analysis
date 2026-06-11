# -*- coding: utf-8 -*-
import pandas as pd
import sys

print('Loading Excel files...')
df_v2 = pd.read_excel('backtest_super_patterns_filtered_v2.xlsx', sheet_name=0)
df_wl = pd.read_excel('winner_loser_analysis.xlsx', sheet_name=0)

print('Merging...')
df_merged = pd.merge(df_v2, df_wl[['Signal Date', 'Stock Name', 'RSI(14)', '20MA Disparity (%)', 'Volume Spike (Times)', 'Smart Money Flow (3 Days)']], on=['Signal Date', 'Stock Name'], how='left')

losers = df_merged[df_merged['D+5 Return (%)'] < 0]
winners = df_merged[df_merged['D+5 Return (%)'] > 0]

with open('scratch/losers_analysis_result.txt', 'w', encoding='utf-8') as f:
    f.write('=== Losers (D+5 < 0) Characteristics ===\n')
    f.write(f'Count: {len(losers)}\n')
    f.write(f'Top Themes:\n{losers["Theme"].value_counts().head()}\n')
    f.write(f'Top Patterns:\n{losers["Pattern"].value_counts().head()}\n')
    f.write(f'Avg RSI: {losers["RSI(14)"].mean():.2f}\n')
    f.write(f'Avg 20MA Disparity: {losers["20MA Disparity (%)"].mean():.2f}%\n')
    
    f.write('\n=== Winners (D+5 > 0) Characteristics ===\n')
    f.write(f'Count: {len(winners)}\n')
    f.write(f'Top Themes:\n{winners["Theme"].value_counts().head()}\n')
    f.write(f'Top Patterns:\n{winners["Pattern"].value_counts().head()}\n')
    f.write(f'Avg RSI: {winners["RSI(14)"].mean():.2f}\n')
    f.write(f'Avg 20MA Disparity: {winners["20MA Disparity (%)"].mean():.2f}%\n')

print('Analysis complete. Results in scratch/losers_analysis_result.txt')
