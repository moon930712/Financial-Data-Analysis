import pandas as pd

def main():
    excel_path = 'winner_loser_analysis.xlsx'
    
    print("Loading raw data...")
    df_raw = pd.read_excel(excel_path)

    # 요약 통계 산출
    summary = df_raw.groupby('Winner/Loser').agg(
        Count=('Stock Name', 'count'),
        Avg_RSI=('RSI(14)', 'mean'),
        Avg_20MA_Disparity=('20MA Disparity (%)', 'mean'),
        Avg_Volume_Spike=('Volume Spike (Times)', 'mean'),
        Avg_Smart_Money=('Smart Money Flow (3 Days)', 'mean')
    ).round(2).reset_index()
    
    # 열 이름 한글로 변경
    summary.columns = [
        '구분(Winner/Loser)', 
        '종목 수', 
        '평균 당일 RSI(14)', 
        '평균 20일 이격도 (%)', 
        '평균 거래대금 폭증 비율 (배)', 
        '외국인+기관 3일 순매수 평균 (주)'
    ]

    # 두 시트로 저장
    with pd.ExcelWriter(excel_path) as writer:
        df_raw.to_excel(writer, sheet_name='Raw Data', index=False)
        summary.to_excel(writer, sheet_name='Summary', index=False)
        
    print(f"Successfully saved to {excel_path} with 2 sheets.")

if __name__ == '__main__':
    main()
