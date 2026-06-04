import pandas as pd

target_patterns = [
    "최상위 -> 상위 -> 최상위",
    "최하위 -> 최하위 -> 최하위",
    "중하위 -> 최하위 -> 최하위",
    "하위 -> 최하위 -> 최하위",
    "최상위 -> 최상위 -> 최상위",
    "하위 -> 최하위 -> 하위",
    "중상위 -> 최상위 -> 최상위",
    "최하위 -> 최하위 -> 하위",
    "상위 -> 중위 -> 중위",
    "상위 -> 최상위 -> 최상위"
]

def run_analysis():
    df = pd.read_excel('reverse_pattern_analysis.xlsx', sheet_name='Raw Data')
    
    # Filter for target patterns
    df_filtered = df[df['Pattern'].isin(target_patterns)]
    
    results = []
    
    for pattern in target_patterns:
        df_p = df_filtered[df_filtered['Pattern'] == pattern]
        if df_p.empty:
            continue
            
        theme_counts = df_p['Theme Name'].value_counts()
        top_themes = theme_counts.head(5)
        
        print(f"[{pattern}] - 총 {len(df_p)}회 발생")
        for i, (theme, count) in enumerate(top_themes.items(), 1):
            print(f"  {i}위: {theme} ({count}회)")
        print()

if __name__ == "__main__":
    run_analysis()
