from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import os

def set_font(run, font_name, size=None, bold=False, color=None):
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    if size:
        run.font.size = Pt(size)
    if bold:
        run.font.bold = True
    if color:
        run.font.color.rgb = color

def create_enhanced_v2_report():
    doc = Document()
    
    # 기본 폰트 설정
    style = doc.styles['Normal']
    font = style.font
    font.name = '맑은 고딕'
    font.size = Pt(11)

    # === [제목 섹션] ===
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run('퀀트 투자 전략 개발 및 성능 분석 결과 보고서')
    set_font(run, '맑은 고딕', size=22, bold=True, color=RGBColor(44, 62, 80))
    
    info_para = doc.add_paragraph()
    info_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = info_para.add_run('작성일: 2026. 04. 13.\n분석 도구: Python / PostgreSQL / Gemini 3.1 Pro')
    set_font(run, '맑은 고딕', size=10, color=RGBColor(127, 140, 141))
    
    doc.add_paragraph('\n')

    # === [1. 개요] ===
    doc.add_heading('1. 개요 (Executive Summary)', level=1)
    p = doc.add_paragraph(
        '본 보고서는 한국 시장 내 저평가된 우량주를 발굴하여 반등 시 수익을 극대화하는 '
        '[가치 턴어라운드(Value Turnaround)] 모델의 개발 과정과 성능 분석 결과를 기록한 문서입니다. '
        '전통적인 가치 평가 모델을 기반으로 하되, 최근 주도주에서 나타나는 수급 집중 현상을 포착하기 위해 '
        '가중치를 최적화하여 안정성과 수익성을 동시에 지향합니다.'
    )
    p.paragraph_format.space_after = Pt(12)

    # === [2. 전략 로직 구성] ===
    doc.add_heading('2. 전략 로직 및 핵심 파라미터', level=1)
    doc.add_paragraph('본 모델은 다음의 5가지 핵심 요소를 결합하여 종합 점수를 산출합니다.', style='List Bullet')
    
    bullets = [
        ('가치 (Value):', '업종 내 상대적 PBR 순위를 통해 섹터별 저평가 종목 선별'),
        ('수익성 (Profitability):', 'ROE(자기자본이익률) 백분위를 통해 이익 창출 능력이 우수한 기업 선별'),
        ('수급 (Momentum):', '거래량 변화량을 통한 에너지 응축 및 반등 시그널 포착'),
        ('리포트 폭발 (Burst):', '최근 1개월 내 증권사 리포트 집중도를 통한 시장 관심도 측정'),
        ('투자 심리 (Sentiment):', '최근 투자심리 및 리서치 의견을 반영한 리스크 필터링')
    ]
    
    for head, text in bullets:
        p = doc.add_paragraph(style='List Bullet 2')
        run = p.add_run(head)
        run.bold = True
        p.add_run(f' {text}')

    # --- [추가 내용: 이원화 전략] ---
    doc.add_heading('2.5. 이원화 전략 (Two-Track Strategy)', level=2)
    doc.add_paragraph(
        '본 전략은 "종목 선정"과 "매수 타이밍"을 분리하여 관리하는 이원화 구조를 가집니다.'
    )
    doc.add_paragraph(
        '• 종목 선정 (Selection): PBR과 ROE를 통해 가격이 저렴하면서도 돈을 벌 줄 아는 우량한 종목을 골라내는 장기적 관점의 필터입니다.',
        style='List Bullet'
    )
    doc.add_paragraph(
        '• 매수 시점 (Timing): 거래량, 투자심리, 리포트 폭발 지표를 통해 지루한 횡보를 끝내고 반등을 시작하는 시점을 포착하여 투자 효율을 극대화합니다.',
        style='List Bullet'
    )

    # --- [추가 내용: PBR 선정 사유] ---
    doc.add_heading('2.6. PBR 지표 선정 사유 및 기대 효과', level=2)
    doc.add_paragraph(
        '전통적인 PER(주가수익비율) 대신 PBR을 주된 가치 지표로 선택한 이유는 다음과 같습니다.'
    )
    doc.add_paragraph(
        '• 하방 경직성 확보: 턴어라운드 종목은 실적 악화로 인해 PER이 왜곡된 경우가 많습니다. '
        '반면 PBR은 기업이 보유한 순자산이라는 명확한 기준(안전 마진)을 제시하여 하락장에서의 방어력이 뛰어납니다.',
        style='List Bullet'
    )
    doc.add_paragraph(
        '• 자산 가치 재평가 공략: "자산을 헐값에 사고(PBR), 수익성 개선(ROE)이 확인될 때 매수하는" 전략을 통해 손익 구조상 비대칭적으로 유리한 투자가 가능해집니다.',
        style='List Bullet'
    )

    # === [3. 업종별 세분화 분석의 필연성] ===
    doc.add_heading('3. 업종별 세분화 분석의 중요성', level=1)
    doc.add_paragraph(
        '업종별로 자산 구조와 마진 상한선이 다르므로, 절대적 수치보다는 업종 내 상대적 순위를 사용하는 것이 퀀트 모델의 정교함을 결정짓습니다.'
    )
    
    doc.add_paragraph(
        '• 밸류에이션 격차 해소: 제조업(설비 기반, 저PBR)과 IT/바이오(IP 기반, 고PBR) 간의 구조적 차이를 인정하고, '
        '각 섹터 내에서 가장 우수한 종목을 추출하여 포트폴리오의 균형을 유지합니다.',
        style='List Bullet 2'
    )

    # === [4. 백테스트 결과 분석] ===
    doc.add_heading('4. 시장 상황별 백테스트 결과 분석', level=1)
    
    doc.add_paragraph('[테스트 A] 상승 장세 (2025. 04. 기준)', style='List Bullet')
    doc.add_paragraph('• 12개월 누적 수익률: +40.35%', style='List Bullet 2')
    
    doc.add_paragraph('[테스트 B] 횡보 장세 (2024. 02. 기준)', style='List Bullet')
    doc.add_paragraph('• 12개월 누적 수익률: -9.36% (시장 지수 대비 선방)', style='List Bullet 2')

    # === [5. 최종 확정 가중치 및 설정] ===
    doc.add_heading('5. 최종 확정 가중치 (Current Optimization)', level=1)
    doc.add_paragraph('현재 시장의 주도주 교체 흐름을 기민하게 반영하기 위한 최종 가중치 설정입니다.')
    
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = '평가 항목'
    hdr_cells[1].text = '가중치 (%)'
    hdr_cells[2].text = '전략적 역할'
    
    for cell in hdr_cells:
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    data = [
        ('수급 (거래량 모멘텀)', '30%', '에너지 응축 및 반등 신호 포착'),
        ('가치 (Industry PBR)', '20%', '안전 마진 및 상대적 저평가'),
        ('수익성 (ROE)', '20%', '이익 창출 능력 및 우량성 검증'),
        ('리포트 폭발 (Burst)', '20%', '기관/전문가 그룹의 집중 관심'),
        ('투자심리 (Sentiment)', '10%', '대중 심리 및 필터링 보조')
    ]
    
    for item, weight, desc in data:
        row_cells = table.add_row().cells
        row_cells[0].text = item
        row_cells[1].text = weight
        row_cells[2].text = desc
        row_cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph('\n')

    # === [6. 결론] ===
    doc.add_heading('6. 결론 및 향후 기대 효과', level=1)
    doc.add_paragraph(
        '본 모델은 단순한 저평가주 발굴을 넘어, 업종 특성을 반영하고 시장의 수급 흐름을 타는 지능형 가치 투자 전략입니다. '
        '특히 이번에 정립된 20/20/30/10/20 가중치 모델은 주도 섹터의 변화를 가장 빠르게 포착하면서도 '
        'PBR과 ROE를 통해 리스크를 관리하는 실전 중심의 최적화된 결과물입니다.'
    )

    # 파일 저장
    output_path = r'c:\Users\Hubnet\antigravity\results\strategy_report_final_v6.docx'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    print(f"Enhanced Report generated at: {output_path}")

if __name__ == "__main__":
    create_enhanced_v2_report()
