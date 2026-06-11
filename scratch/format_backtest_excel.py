import pandas as pd

def main():
    print("Loading raw data...")
    df_raw = pd.read_excel('backtest_super_patterns_stocks.xlsx')

    # 요약 통계 계산
    summary = df_raw.groupby('Pattern').agg(
        Total_Count=('Stock Name', 'count'),
        Win_Count_D5=('D+5 Return (%)', lambda x: (x > 0).sum()),
        Win_Count_AnyDay=('Max 5-Day Return (%)', lambda x: (x > 0).sum()),
        Avg_D5_Return=('D+5 Return (%)', 'mean')
    ).reset_index()

    summary['D+5 종가 승률 (%)'] = round((summary['Win_Count_D5'] / summary['Total_Count']) * 100, 2)
    summary['5일 내 고점 승률 (%)'] = round((summary['Win_Count_AnyDay'] / summary['Total_Count']) * 100, 2)
    summary['평균 D+5 수익률 (%)'] = round(summary['Avg_D5_Return'], 2)

    summary = summary[['Pattern', 'Total_Count', 'D+5 종가 승률 (%)', '5일 내 고점 승률 (%)', '평균 D+5 수익률 (%)']]
    summary.columns = ['테마 패턴', '검색된 종목 수', 'D+5 종가 승률 (%)', '5일 내 고점 승률 (%)', '평균 D+5 수익률 (%)']

    # 정렬
    sort_order = {
        '6등급 -> 4등급 -> 1등급': 1,
        '4등급 -> 3등급 -> 1등급': 2,
        '4등급 -> 2등급 -> 2등급': 3
    }
    summary['sort_key'] = summary['테마 패턴'].map(sort_order)
    summary = summary.sort_values('sort_key').drop(columns='sort_key')

    # 두 시트로 저장
    excel_path = 'backtest_super_patterns_stocks.xlsx'
    with pd.ExcelWriter(excel_path) as writer:
        df_raw.to_excel(writer, sheet_name='Raw Data', index=False)
        summary.to_excel(writer, sheet_name='Summary', index=False)
        
    print(f"Successfully saved to {excel_path} with 2 sheets.")

if __name__ == '__main__':
    main()
