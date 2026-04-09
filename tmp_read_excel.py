import pandas as pd
import json

file_path = r'C:\Users\Hubnet\antigravity\excel\Finex_프로젝트정리_v0.3_문기성2.xlsx'

xl = pd.ExcelFile(file_path)

output = []
output.append(f"Sheet names: {xl.sheet_names}")

for sheet in xl.sheet_names:
    output.append(f"\n--- Sheet: {sheet} ---")
    df = xl.parse(sheet, nrows=5)
    output.append(f"Columns: {list(df.columns)}")
    output.append(df.head(3).to_string())

with open(r'c:\Users\Hubnet\antigravity\excel_summary.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

