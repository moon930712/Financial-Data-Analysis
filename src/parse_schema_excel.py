import pandas as pd
import json

file_path = '마스터테이블정의서_20250807.xlsx'
output_md = r'C:\Users\Hubnet\.gemini\antigravity\brain\c6a29c15-f6c2-462d-a094-3b676203b19d\database_schema_knowledge.md'

print("Loading excel file...")
try:
    xl = pd.ExcelFile(file_path)
    sheet_names = xl.sheet_names
    
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("# Database Schema Knowledge\n\n")
        f.write("This artifact contains the extracted schema from the provided master table definition file.\n\n")
        
        for sheet in sheet_names:
            print(f"Processing sheet: {sheet}")
            df = xl.parse(sheet).head(20) # Just parse head to get structure, maybe check columns
            f.write(f"## Sheet: {sheet}\n")
            f.write(f"**Columns:** {', '.join([str(c) for c in df.columns])}\n\n")
            
            # Print sample rows
            if not df.empty:
                f.write(df.to_markdown(index=False))
                f.write("\n\n")
            else:
                f.write("Empty sheet.\n\n")
                
    print("Successfully generated markdown artifact.")
except Exception as e:
    print(f"Error: {e}")
