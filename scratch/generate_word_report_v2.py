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

def create_professional_report():
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
    
    doc.add_paragraph('\n') # 간격

    # === [1. 개요] ===
    doc.add_heading('1. 개요 (Executive Summary)', level=1)
    p = doc.add_paragraph(
        '본 보고서는 한국 시장(KOSPI/KOSDAQ) 내 저평가된 우량주를 발굴하여 반등 시 수익을 극대화하는 '
        '[가치 턴어라운드(Value Turnaround)] 모델의 개발 과정과 성능 분석 결과를 기록한 문서입니다. '
        '재무 건전성(ROE), 가치 지표(PBR), 투자 심리 및 수급 데이터를 결합하여 시장 상황에 유연하게 대응하는 최적의 가중치 모델을 도출하였습니다.'
    )
    p.paragraph_format.space_after = Pt(12)

    # === [2. 전략 로직 구성] ===
    doc.add_heading('2. 전략 로직 및 핵심 파라미터', level=1)
    doc.add_paragraph('본 모델은 다음의 4가지 퀀트 요소를 결합하여 종합 점수를 산출합니다.', style='List Bullet')
    
    bullets = [
        ('가치 (Value):', '업종 내 상대적 PBR 순위를 통해 섹터별 저평가 종목 선별'),
        ('수익성 (Profitability):', 'ROE(자기자본이익률) 백분위를 통해 이익 창출 능력이 우수한 기업 선별'),
        ('수급 (Momentum):', '거래량 변화량(최근 1주 vs 과거 12주)을 통한 에너지 응축 종목 포착'),
        ('투자 심리 (Sentiment):', '최근 투자심리 지수를 반영하여 시장 대중의 관심도 측정')
    ]
    
    for head, text in bullets:
        p = doc.add_paragraph(style='List Bullet 2')
        run = p.add_run(head)
        run.bold = True
        p.add_run(f' {text}')

    # === [3. 업종별 세분화 분석의 필연성] ===
    doc.add_heading('3. 업종별 세분화 분석의 중요성', level=1)
    doc.add_paragraph(
        '종목의 절대적 순위가 아닌 업종 내 상대적 순위를 핵심 지표로 사용하는 것은 퀀트 모델의 정교함을 결정짓는 핵심 요소입니다.'
    )
    
    # 밸류에이션 격차 해소 상세 설명
    p = doc.add_paragraph('3.1. 섹터별 밸류에이션 격차 해소', style='List Number')
    p.paragraph_format.space_before = Pt(6)
    
    expl_p = doc.add_paragraph(style='Normal')
    expl_p.add_run('업종별로 PBR(주가순자산비율)의 정상 범위는 산업의 특성에 따라 완전히 다릅니다.').italic = True
    
    doc.add_paragraph(
        '• 자산 구성의 차이: 제조업/조선업 등 장치 산업은 공장, 설비 등 막대한 유형자산이 장부가액의 대부분을 차지하여 PBR이 낮게 형성됩니다. '
        '반면, IT/바이오 등 지식 기반 산업은 기술력과 지식재산권 등 무형자산을 기반으로 하므로 장부가액 대비 시가총액이 매우 높게 평가(고PBR)되는 것이 정상적입니다.',
        style='List Bullet 2'
    )
    doc.add_paragraph(
        '• 성장성 기대치: 미래 수익에 대한 기대감이 선반영되는 고성장 산업은 현재 자산 가치보다 높은 프리미엄을 받는 반면, 성숙 산업은 자산 가치 근처에서 주가가 형성됩니다. '
        '업종 구분이 없으면 저PBR 순위는 항상 자산 비중이 높은 업종이 독점하게 되어 공정한 비교가 불가능합니다.',
        style='List Bullet 2'
    )

    doc.add_paragraph('3.2. 리스크 분산 및 섹터 로테이션 대응', style='List Number')
    doc.add_paragraph(
        '특정 업황이 호조를 보일 때 특정 섹터가 리스트를 독차지하는 쏠림 현상을 방지합니다. '
        '전 업종에 걸쳐 골고루 우수한 종목을 선별함으로써 포트폴리오의 안정성을 높이고 하락장에서의 방어력을 강화합니다.',
        style='List Bullet 2'
    )

    # === [4. 백테스트 결과 분석] ===
    doc.add_heading('4. 시장 상황별 백테스트 결과 분석', level=1)
    
    doc.add_paragraph('[테스트 A] 상승/주도 장세 (2025. 04. 기준)', style='List Bullet')
    doc.add_paragraph('• 12개월 누적 수익률: +40.35%', style='List Bullet 2')
    doc.add_paragraph('• 분석: 수급 모멘텀이 강한 시기에 전략의 폭발력이 극대화됨을 확인하였습니다.', style='List Bullet 2')
    
    doc.add_paragraph('[테스트 B] 횡보/조정 장세 (2024. 02. 기준)', style='List Bullet')
    doc.add_paragraph('• 12개월 누적 수익률: -9.36% (KOSPI 대비 방어)', style='List Bullet 2')
    doc.add_paragraph('• 분석: 단순 가치 모델(-11.39%)보다 수급을 가미한 모델의 방어력이 더 우수했으며, 최소한의 시장 관심이 있어야 하락장에서 탄력이 유지됨을 확인하였습니다.', style='List Bullet 2')

    # === [5. 최종 확정 가중치 및 추천 설정] ===
    doc.add_heading('5. 최종 확정 가중치 (Proposed Model)', level=1)
    
    table = doc.add_table(rows=1, cols=3)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = '평가 항목'
    hdr_cells[1].text = '가중치 (%)'
    hdr_cells[2].text = '세부 설명'
    
    # 헤더 배경색 및 폰트 (전문적으로 보이기 위해)
    for cell in hdr_cells:
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    data = [
        ('업종 내 저평가 (Value)', '30%', '산업 평균 대비 상대적 가치 평가'),
        ('수익성 (ROE)', '25%', '안정적인 이익 창출 및 자본 효율성'),
        ('수급 (거래량 모멘텀)', '30%', '에너지 응축 및 반등 시그널 포착'),
        ('투자심리 (Sentiment)', '15%', '시장 분위기 및 리포트 의견 반영')
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
        '본 모델은 단순한 저평가주 발굴을 넘어, 업종의 특성을 반영하고 시장의 수급 흐름을 타는 지능형 가치 투자 전략입니다. '
        '특히 이번에 정립된 30/25/30/15 가중치는 상승장과 조정장 모두에서 밸런스 있는 성과를 보여주었으며, '
        '향후 실제 운용 파이프라인에 적용 시 시장 대비 안정적인 초과 수익(Alpha)을 창출할 것으로 기대됩니다.'
    )

    # 파일 저장
    output_path = r'c:\Users\Hubnet\antigravity\results\strategy_report_v2.docx'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    print(f"Professional Report generated at: {output_path}")

if __name__ == "__main__":
    create_professional_report()
