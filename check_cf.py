from openpyxl import load_workbook

file_path = r'C:\Users\Hubnet\antigravity\excel\Finex_프로젝트정리_v0.3_문기성2.xlsx'
wb = load_workbook(file_path)
ws = wb['MACD 적용 수기 검증결과']

print(f"Conditional Formattings in '{ws.title}':")
for cf in ws.conditional_formatting:
    print(f"Cells: {cf.cells}")
    for rule in cf.rules:
        print(f"  Type: {rule.type}, Operator: {rule.operator}, Formula: {rule.formula}")
