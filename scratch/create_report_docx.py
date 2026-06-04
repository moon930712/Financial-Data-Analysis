import os
import sys

try:
    import docx
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    print("python-docx is not installed. Please install it with 'pip install python-docx'")
    sys.exit(1)

def create_report():
    output_dir = r"C:\Users\Hubnet\.gemini\antigravity\brain\91ab22e2-52ba-400e-bf04-bc57c65e12a1"
    output_path = os.path.join(output_dir, "Theme_Rotation_Report.docx")

    doc = docx.Document()

    # Title
    title = doc.add_heading('MACD 기반 테마별 순환매 마스터 분석 모델 기획서', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 1. 배경 및 필요성
    doc.add_heading('1. 배경 및 필요성', level=1)
    p = doc.add_paragraph()
    p.add_run("단순히 테마 내 기술적 신호의 '개수'만 합산할 경우, 종목 수가 많은 대형 테마(예: 반도체, 2차전지 등)가 영구적으로 상위권을 독식하는 문제가 발생합니다. ").bold = False
    p.add_run("\n이를 극복하고 대장주 편향성을 제어하면서 작지만 강하게 튀어오르는 '신규 주도 테마'를 찾기 위해, ").bold = False
    p.add_run("비율 기반 표준화(Standardization)").font.color.rgb = RGBColor(0, 102, 204)
    p.add_run(" 및 ").bold = False
    p.add_run("시가총액 가중치(Value-Weighting)").font.color.rgb = RGBColor(0, 102, 204)
    p.add_run(" 모델을 도입하였습니다. 이 모델은 테마의 크기에 얽매이지 않고 실질적인 시장의 자금 이동을 정확하게 진단합니다.").bold = False

    # 2. 핵심 계산 방법론 및 산식
    doc.add_heading('2. 핵심 계산 방법론 및 산식', level=1)
    
    doc.add_heading('2.1. 4대 핵심 신호 및 가중치 (Z-Score ±1.0 적용)', level=2)
    p = doc.add_paragraph()
    p.add_run("• MACD음수맥스 (바닥 반전): ").bold = True
    p.add_run("+10점 (강한 초기 턴어라운드 기대)\n")
    p.add_run("• 골든크로스 (추세 확인): ").bold = True
    p.add_run("+7점 (상승 모멘텀 강화)\n")
    p.add_run("• MACD양수맥스 (고점 반전): ").bold = True
    p.add_run("-5점 (상승 동력 둔화 및 과열 주의)\n")
    p.add_run("• 데드크로스 (추세 역전): ").bold = True
    p.add_run("-10점 (하락 전환 및 강한 매도세)")

    doc.add_heading('2.2. 로테이션 스코어 산출식 (시총 가중치)', level=2)
    p = doc.add_paragraph("개별 종목이 Тема 전체에서 차지하는 '시가총액 비중'을 곱하여 개별 종목의 득점을 산출합니다.\n")
    p.add_run("▶ 개별 종목 기여도 = (발생 신호 점수) × (해당 종목 시가총액 / 테마의 전체 시가총액)\n").bold = True
    p.add_run("▶ 업종 로테이션 스코어 = 테마 내 신호 발생 종목들의 기여도 총합(SUM)").bold = True

    doc.add_heading('2.3. 국면 진단 기준', level=2)
    p = doc.add_paragraph()
    p.add_run("• 스코어 5.0 이상: ").bold = True; p.add_run("강력 회복\n")
    p.add_run("• 스코어 1.0 이상: ").bold = True; p.add_run("회복 진행\n")
    p.add_run("• 스코어 -1.0 이하: ").bold = True; p.add_run("하락 전환\n")
    p.add_run("• 스코어 -5.0 이하: ").bold = True; p.add_run("강한 하락\n")
    p.add_run("• 그 외: ").bold = True; p.add_run("중립/혼조")

    # 3. 모델의 신뢰도 확보 장치
    doc.add_heading('3. 통계적 신뢰도 확보 장치 (필터링 방패)', level=1)
    
    p = doc.add_paragraph()
    p.add_run("이 모델은 단 1개의 소형주가 급상승하여 100개짜리 대형 테마를 누르는 현상을 방지하기 위해 다음과 같은 이중 안전장치를 갖추고 있습니다.\n\n")
    
    p.add_run("1) 노이즈 차단 (최소 3종목 이상 조건)\n").bold = True
    p.add_run("단 1~2개 종목만 신호를 보인 것은 테마의 움직임이 아닌 '개별 종목 호재'로 간주하여 점수 산출에서 아예 제외합니다. 오직 신호가 발생한 종목이 3개 이상인 테마만 분석 대상이 됩니다.\n\n")

    p.add_run("2) 대형주 편향 차단 (비율 표준화의 이유)\n").bold = True
    p.add_run("100개짜리 테마에서 10개가 오른 것과 10개짜리 테마에서 10개가 오른 것을 공정하게 비교하려면 '비율(%)'이 필요합니다. 우리는 분모에 '테마 전체 시가총액'을 두어 덩치 계급장을 떼고 '파이 안에서의 비중'이라는 동일한 체급에서 순위를 매겼습니다.\n\n")

    p.add_run("3) 대장주 보호 가중치\n").bold = True
    p.add_run("비율로 묶어두면서도 테마의 심장인 '대장주'가 움직일 때는 점수가 폭발적으로 상승하도록 가중치 시스템을 적용하여 지수 견인력을 담아냈습니다.")

    # 4. 시뮬레이션 계산 예시
    doc.add_heading('4. 산출 시뮬레이션 예시 (전선 테마)', level=1)
    p = doc.add_paragraph("총 시총 10조 원인 전선 테마에 10개의 종목이 있고, 오늘 3개 종목에서 신호가 발생했다고 가정한 계산 결과입니다.\n")

    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = '구분'
    hdr_cells[1].text = '종목 정보 및 비중'
    hdr_cells[2].text = '발생 신호 (기본 점수)'
    hdr_cells[3].text = '스코어 기여도계산'

    row_cells = table.add_row().cells
    row_cells[0].text = 'A종목 (대장주)'
    row_cells[1].text = '시총 6조 (비중 60%)'
    row_cells[2].text = '골든크로스 (+7점)'
    row_cells[3].text = '7 × 0.6 = +4.2점'

    row_cells = table.add_row().cells
    row_cells[0].text = 'B종목 (중견주)'
    row_cells[1].text = '시총 3조 (비중 30%)'
    row_cells[2].text = 'MACD음수맥스 (+10점)'
    row_cells[3].text = '10 × 0.3 = +3.0점'

    row_cells = table.add_row().cells
    row_cells[0].text = 'C종목 (소형주)'
    row_cells[1].text = '시총 1천억 (비중 1%)'
    row_cells[2].text = '데드크로스 (-10점)'
    row_cells[3].text = '-10 × 0.01 = -0.1점'

    p2 = doc.add_paragraph("\n[최종 진단 결과]\n")
    p2.add_run("▶ 신호 발생 종목수: ").bold = True
    p2.add_run("3개 (3종목 이상 조건 통과)\n")
    p2.add_run("▶ 업종 로테이션 스코어: ").bold = True
    p2.add_run("4.2 + 3.0 - 0.1 = 7.1점\n")
    p2.add_run("▶ 국면 판정: ").bold = True
    p2.add_run("스코어 5.0 이상이므로 '강력 회복' 국면으로 진단. 소형주 C가 폭락하더라도, 비중이 거대한 대장주 A와 B가 이끄는 강력한 자금 유입세를 정확하게 포착할 수 있습니다.")

    doc.save(output_path)
    print(f"Success! Report generated at: {output_path}")

if __name__ == '__main__':
    create_report()
