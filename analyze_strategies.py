import pandas as pd
import numpy as np

file_path = r'C:\Users\Hubnet\antigravity\excel\Finex_프로젝트정리_v0.3_문기성2.xlsx'

# Load the summary sheet
df = pd.read_excel(file_path, sheet_name='MACD 적용 수기 검증결과')
df.columns = df.columns.str.strip()

# Helper function to clean numeric strings
def clean_numeric(val):
    if pd.isna(val) or val == '':
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Remove %, commas, and common notation
        val = val.replace('%', '').replace(',', '').strip()
        try:
            return float(val)
        except:
            return 0.0
    return 0.0

# Return columns: D+1 수익률(%) to D+10 수익률(%)
# Win rate columns: D+1 승률(%) to D+10 승률(%)
return_cols = [f'D+{i} 수익률(%)' for i in range(1, 11)]
win_rate_cols = [f'D+{i} 승률(%)' for i in range(1, 11)]

# Apply cleaning
for col in return_cols + win_rate_cols:
    if col in df.columns:
        df[col] = df[col].apply(clean_numeric)

# Ensure '종목수' is numeric
df['종목수'] = pd.to_numeric(df['종목수'], errors='coerce').fillna(0)

# Aggregation
analysis = []
for strategy, group in df.groupby('투자전략(상세)'):
    if str(strategy).lower() == 'nan' or strategy == '': continue
    
    avg_returns = group[return_cols].mean()
    avg_win_rates = group[win_rate_cols].mean()
    total_trades = group['종목수'].sum()
    
    # Best performance day (max return)
    max_avg_return = avg_returns.max()
    best_day = avg_returns.idxmax()
    peak_win_rate = avg_win_rates[best_day.replace('수익률', '승률')]
    
    # Growth shape: Last day - first day
    momentum = avg_returns['D+10 수익률(%)'] - avg_returns['D+1 수익률(%)']
    
    analysis.append({
        '전략': strategy,
        '누적종목수': total_trades,
        'D+1평균': avg_returns['D+1 수익률(%)'],
        '최대평균': max_avg_return,
        '최종평균': avg_returns['D+10 수익률(%)'],
        '피크시점': best_day,
        '피크승률': peak_win_rate,
        '모멘텀': momentum
    })

results = pd.DataFrame(analysis)

# Comprehensive Scoring (Higher is better)
# (Max Return * 50) + (Peak Win Rate * 30) + (Momentum * 20)
results['평가점수'] = (results['최대평균'] * 50) + (results['피크승률'] * 30) + (results['모멘텀'] * 20)

results = results.sort_values(by='평가점수', ascending=False)

print("\n--- [투자 전략 데이터 기반 성과 보고서] ---")
print(results[['전략', '누적종목수', 'D+1평균', '최대평균', '피크시점', '피크승률', '평가점수']].to_string(index=False))

print("\n--- [데이터 분석 결과 및 가이드라인] ---")

# Best
top = results.iloc[0]
print(f"🥇 [최고 성과 전략] -> {top['전략']}")
print(f" - 최대 수익률: {top['최대평균']:.2f}% (피크 시점: {top['피크시점']})")
print(f" - 해당 시점 승률: {top['피크승률']*100:.1f}%")
print(f" - 특징: 진입 후 {top['피크시점']}까지 가장 탄력적인 상승세를 보이며 승률 또한 매우 안정적입니다.\n")

# Worst (filter for ones with enough data)
significant_results = results[results['누적종목수'] > 1]
if not significant_results.empty:
    worst = significant_results.iloc[-1]
    print(f"🚫 [삭제/수정 권고 전략] -> {worst['전략']}")
    print(f" - 평가점수: {worst['평가점수']:.2f}")
    print(f" - 특징: 평균 수익률이 마이너스이거나, 시간이 지날수록 손실이 확대되는(모멘텀 부재) 경향이 뚜렷합니다.")
else:
    print("⚠️ 데이터가 부족하여 삭제 권고 전략을 선정할 수 없습니다.")
