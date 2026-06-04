import pandas as pd

excel_path = 'pattern_grade_transition.xlsx'

print("=== 1. Summary Sheet (First 5 Rows) ===")
df_summary = pd.read_excel(excel_path, sheet_name='Summary')
print(df_summary.head(5).to_string(index=False))

print("\n=== 2. Distribution Sheet (First 5 Rows) ===")
df_dist = pd.read_excel(excel_path, sheet_name='Distribution')
print(df_dist.head(5).to_string(index=False))

print("\n=== 3. Theme Distribution Sheet (First 10 Rows) ===")
df_theme = pd.read_excel(excel_path, sheet_name='Theme Distribution')
print(df_theme.head(10).to_string(index=False))
