import pandas as pd

excel_path = 'pattern_grade_transition.xlsx'

print("=== 1. Distribution Sheet (First 15 Rows) ===")
df_dist = pd.read_excel(excel_path, sheet_name='Distribution')
print(df_dist.head(15).to_string(index=False))

print("\n=== 2. Optimal Path Sheet (First 10 Rows) ===")
df_path = pd.read_excel(excel_path, sheet_name='Optimal Path')
print(df_path.head(10).to_string(index=False))
