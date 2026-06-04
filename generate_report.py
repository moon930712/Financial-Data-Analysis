import os
import sys
import subprocess

def install_requirements():
    packages = ["matplotlib", "python-docx", "numpy", "pandas", "openpyxl"]
    for pkg in packages:
        try:
            __import__(pkg if pkg != "python-docx" else "docx")
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_requirements()

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# 한국어 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
os.makedirs("result", exist_ok=True)

def generate_phase_diagram():
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.linspace(0, 2 * np.pi, 500)
    y = -np.sin(x)
    
    ax.axhline(0, color='black', linewidth=1.5, linestyle='--')
    ax.plot(x, y, color='black', linewidth=2)
    
    ax.fill_between(x, y, 0, where=(x >= 0) & (x < np.pi/2), color='blue', alpha=0.2, label='제2국면(하락기)')
    ax.fill_between(x, y, 0, where=(x >= np.pi/2) & (x < np.pi), color='green', alpha=0.2, label='제1국면(회복기)')
    ax.fill_between(x, y, 0, where=(x >= np.pi) & (x < 3*np.pi/2), color='red', alpha=0.2, label='제3국면(상승기)')
    ax.fill_between(x, y, 0, where=(x >= 3*np.pi/2) & (x <= 2*np.pi), color='orange', alpha=0.2, label='제4국면(둔화기)')

    ax.text(np.pi/4, -0.5, '2. 하락기\n(지표<0, 하락추세)', ha='center', va='center', fontsize=12, fontweight='bold')
    ax.text(3*np.pi/4, -0.5, '1. 회복기\n(지표<0, 상승전환)', ha='center', va='center', fontsize=12, fontweight='bold')
    ax.text(5*np.pi/4, 0.5, '3. 상승기\n(지표>0, 상승추세)', ha='center', va='center', fontsize=12, fontweight='bold')
    ax.text(7*np.pi/4, 0.5, '4. 둔화기\n(지표>0, 하락전환)', ha='center', va='center', fontsize=12, fontweight='bold')

    ax.set_title('MACD 스윙 사이클에 따른 4대 국면(Phases) 구조도', fontsize=16, fontweight='bold')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_ylabel('MACD 정규화 지표', fontsize=12)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    plt.tight_layout()
    diagram_path = "result/phase_diagram.png"
    plt.savefig(diagram_path, dpi=300)
    plt.close()
    return diagram_path

def generate_word_report(diagram_path, target_date='2026-03-18'):
    doc = Document()
    
    title = doc.add_heading('4국면 테마 순환매 분석 및 데일리 추천 보고서 (v4)', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 1. 정의
    doc.add_heading('1. 정의', level=1)
    doc.add_paragraph('주가 기반의 MACD 히스토그램 로직을 이용해 시장을 주도하는 대장 테마 및 소분류를 명확하게 발굴할 수 있는 모델을 구축하였습니다.')
    doc.add_paragraph('4국면을 자체 제작(회복기->하락기->상승기->둔화기)하였으며, 특히 자본금 및 주가 스케일이 상이한 종목들 간에도 신호의 파워를 표준화하여 정밀 비교가 가능해졌습니다.')

    # 다이어그램
    doc.add_heading('4국면(Phases) 사이클 시각화', level=2)
    doc.add_paragraph('MACD 0선을 기준으로 한 4대 국면의 구조도입니다.')
    doc.add_picture(diagram_path, width=Inches(6.0))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 2. 알고리즘 
    doc.add_heading('2. 분석 알고리즘 개편 개요 (Algorithm Restructuring)', level=1)
    doc.add_heading('📌 국면별 우선순위 배정 사유 (왜 이 순서인가?)', level=2)
    doc.add_paragraph('본 분석 모델은 이미 어깨까지 올라온 종목에 뒤늦게 편승하는 것보다, \'바닥을 다지고 턴어라운드하는 시점\'을 최우선 진입 타점으로 잡는 역발상/선취매 전략을 핵심으로 합니다. 따라서 신규 진입 매력도와 모니터링 시급성에 따라 아래와 같이 순위를 재배치하였습니다.')

    doc.add_paragraph('1순위: 회복기 (최우선 매수 타겟)\n- 정의: MACD 0선 아래(음수)에 위치해 있지만, 하락세가 멈추고 지표가 상승으로 고개를 들기 시작한 상태입니다.\n- 배정 이유: 가장 큰 수익비를 낼 수 있는 완벽한 \'바닥 탈출 구간\'이자 선취매 타이밍이므로 분석 모델에서 가장 먼저(1순위) 노출되도록 배치했습니다.').style = 'List Bullet'
    
    doc.add_paragraph('2순위: 하락기 (관심 종목 편입 대기)\n- 정의: MACD 0선 아래(음수)에서 여전히 지표가 꺾이며 추가적인 하락이 진행 중인 상태입니다.\n- 배정 이유: 얼핏 최악의 상태로 보이지만, 과대 낙폭이 진행 중이기에 \'언제 1순위(회복기)로 턴어라운드 할지\' 바닥 형성 지점을 예의주시해야 하는 예비 타겟들입니다. 따라서 2순위로 두어 지속 모니터링합니다.').style = 'List Bullet'
    
    doc.add_paragraph('3순위: 상승기 (추세 추종 및 보유자 영역)\n- 정의: MACD 0선 위(양수)에 위치하며, 강한 상승 모멘텀을 유지하며 위로 뻗어나가는 상태입니다.\n- 배정 이유: 안정적인 수익 창출 구간이지만, 모멘텀 투자자가 아닌 이상 신규 진입 단가 경쟁력은 회복기 대비 떨어집니다. 따라서 이미 추세에 올라탄 종목 확인을 위해 3순위로 배치합니다.').style = 'List Bullet'
    
    doc.add_paragraph('4순위: 둔화기 (리스크 관리 및 매도 영역)\n- 정의: MACD 0선 위(양수)에 있지만 상승 동력을 잃고 지표가 상승 폭을 반납하는 상태입니다.\n- 배정 이유: 단기 차익 실현 매물이 나오거나 추세가 꺾일 위험이 큰 시점이므로 신규 진입 매력도가 가장 떨어집니다. 이에 최하위(4순위)로 미루어 노출시킵니다.').style = 'List Bullet'

    # 3. 네이버 테마 기반 (장단점)
    doc.add_heading('3. 네이버 테마(Theme) 기반 순환매 분석', level=1)
    doc.add_paragraph('테이블 / 컬럼: company.naver_theme / theme_name')
    doc.add_paragraph('장점: 시장의 트렌드와 세부적인 단기 이슈(예: AI, 2차전지 등)에 민감하게 반응하므로, 시장을 즉흥적으로 이끄는 단기간의 모멘텀 흐름을 빠르게 포착하는 데 매우 유리합니다.').style = 'List Bullet'
    doc.add_paragraph('단점: 테마의 생성과 소멸이 매우 잦기 때문에 장기적인 자금의 안정성을 파악하기 어렵고, 테마명 부여 자체가 포털 시스템의 성향에 따라 주관성이 개입될 수 있어 통계적 관점에서는 일관성이 떨어질 수 있습니다.').style = 'List Bullet'

    # 4. 소분류 기반 (장단점)
    doc.add_heading('4. 소분류 기반 순환매 분석', level=1)
    doc.add_paragraph('테이블 / 컬럼: visual.vsl_krx_stocks_cap / wics_name3')
    doc.add_paragraph('장점: 거래소 상장사가 체계화된 산업 분류(WICS) 표준에 맞추어 배정되어 있기 때문에, 기관이나 외국인의 굵직한 거시적 산업 간 자금 이동 흐름(섹터 로테이션)을 객관적으로 분석하는 데 탁월합니다. 중복 복제 없이 안정적인 종목 카운팅이 가능합니다.').style = 'List Bullet'
    doc.add_paragraph('단점: 기존 네이버 테마처럼 뾰족하고 세밀하게 나뉜 특정 이슈 모멘텀을 즉각적으로 반영하기에는 다소 둔감하며, 같은 섹터 내에서도 전혀 다른 계열의 종목들이 혼재될 가능성이 있습니다.').style = 'List Bullet'

    # 5. 주가 기반 정규화 (정렬)
    doc.add_heading('5. 주가 기반 정규화 (정렬 로직)', level=1)
    doc.add_paragraph('주가 기반 정규화 (Normalization): MACD 히스토그램을 현재 종가로 나누는 비율 수식 ((histogram / close_price) * 100)을 전면 도입하였습니다. 이를 통해 시가총액이나 주가가 1,000원인 종목과 100,000원인 종목 간의 태생적 스케일 차이를 완벽히 상쇄하여 동등한 신호 파워 비교가 가능해졌습니다.').style = 'List Bullet'
    doc.add_paragraph('0선 기준 밀착 정렬 알고리즘: 단순히 값이 큰 순서나 작은 순서가 아닌, 국면의 성격에 맞춘 0선 기준 거리 정렬을 수행합니다. 회복기/하락기(음수)는 파워가 센 순서인 가장 깊은 곳(먼 곳)부터 정렬하고, 상승기/둔화기(양수)는 양수 전환 초기 상태를 파악하기 위해 가장 얕은(가까운) 곳부터 정렬하여 추세 전환의 대장주를 우선 탐색합니다.').style = 'List Bullet'

    # 6. 그라파나 대시보드 작성
    doc.add_heading('6. 그라파나 대시보드 작성', level=1)
    doc.add_paragraph('위에서 설계한 2가지 관점(네이버 테마 및 WICS 섹터)의 국면 매트릭스를 그라파나 현황판에 연동합니다. 대시보드에서는 상단 변수(Variable) 패널을 통해 두 관점 간의 자유로운 스왑 조회가 가능하며, 가장 시의적절하게 자산 배분을 실행할 수 있는 인사이트와 1순위 타겟 종목(회복기 초입)을 제공할 예정입니다.')

    # 7. 소비자 관점의 D+5 수익 마감 확률 기반 데일리 추천
    doc.add_heading('7. 소비자 관점 D+5 수익 마감 확률 기반 데일리 추천', level=1)
    doc.add_paragraph(f'분석 기준일: {target_date}')
    doc.add_paragraph('오늘 진입 시그널(당일 상위 20위 내 진입)이 발생한 대장 테마에 대해, 과거 동일한 3일 랭킹 변동 패턴이 나타났을 때의 소비자 관점 D+5 만기 보유 성과(Hold-to-Maturity) 통계를 실시간으로 연동하여 추천 순위를 구성하였습니다. (Min/Max 리스크 지표를 제외하고 중앙값 및 승률 중심으로 작성되었습니다.)')

    try:
        from generate_daily_signals import get_daily_signals
        df_signals = get_daily_signals(target_date)
        
        if df_signals is not None and not df_signals.empty:
            # 워드 테이블 추가
            table = doc.add_table(rows=1, cols=7)
            table.style = 'Light Shading Accent 1'
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = '추천 테마명'
            hdr_cells[1].text = 'D-day 순위'
            hdr_cells[2].text = '3일 패턴'
            hdr_cells[3].text = '과거 발생(건)'
            hdr_cells[4].text = 'D+5 승률(%)'
            hdr_cells[5].text = 'D+5 중앙값(%)'
            hdr_cells[6].text = 'D+5 평균값(%)'
            
            for index, row in df_signals.iterrows():
                row_cells = table.add_row().cells
                row_cells[0].text = str(row['Theme Name'])
                row_cells[1].text = str(row['Rank(D-day)'])
                row_cells[2].text = str(row['Pattern'])
                row_cells[3].text = str(int(row['Count'])) if not pd.isna(row['Count']) else '0'
                row_cells[4].text = f"{row['D+5 Win Rate (%)']:.1f}%" if not pd.isna(row['D+5 Win Rate (%)']) else 'N/A'
                row_cells[5].text = f"{row['D+5 Return (Median)']:.2f}%" if not pd.isna(row['D+5 Return (Median)']) else 'N/A'
                row_cells[6].text = f"{row['D+5 Return (Average)']:.2f}%" if not pd.isna(row['D+5 Return (Average)']) else 'N/A'
                
            doc.add_paragraph()
            
            # 요약 분석 코멘트
            top_theme = df_signals.iloc[0]
            win_rate = top_theme['D+5 Win Rate (%)']
            median_ret = top_theme['D+5 Return (Median)']
            count = int(top_theme['Count']) if not pd.isna(top_theme['Count']) else 0
            
            summary_p = doc.add_paragraph()
            summary_p.add_run('📌 데일리 리포트 핵심 요약:').bold = True
            doc.add_paragraph(
                f"당일 시그널 발생 테마 중 과거 소비자 관점의 D+5 수익 마감 확률이 가장 유망한 테마는 "
                f"'{top_theme['Theme Name']}'(패턴: {top_theme['Pattern']}) 입니다. "
                f"해당 패턴은 과거에 총 {count}회 관측되었으며, D+5 시점에 최종 수익으로 마감될 확률은 "
                f"{win_rate:.1f}%에 달하고, 수익률 중앙값은 {median_ret:.2f}%를 기록하여 통계적 재현성이 우수한 것으로 분석되었습니다."
            )
        else:
            doc.add_paragraph('당일 시그널이 발생한 테마가 없거나 분석을 수행할 수 없습니다.')
    except Exception as e:
        doc.add_paragraph(f'데일리 추천 테마 데이터를 불러오는 도중 에러가 발생했습니다: {str(e)}')

    report_path = "result/4국면_테마_및_소분류_순환매_분석보고서_v4.docx"
    doc.save(report_path)
    print(f"새로운 보고서(v4)가 성공적으로 생성되었습니다: {report_path}")

if __name__ == "__main__":
    t_date = sys.argv[1] if len(sys.argv) > 1 else '2026-03-18'
    diagram_path = generate_phase_diagram()
    generate_word_report(diagram_path, t_date)
