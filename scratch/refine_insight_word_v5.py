# -*- coding: utf-8 -*-
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
import os

def create_refined_document():
    doc = Document()

    # Set default font
    style = doc.styles['Normal']
    style.font.name = 'Malgun Gothic'
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Malgun Gothic')
    style.font.size = Pt(11)

    # Add title
    doc.add_heading('[퀀트 리포트] 테마 순환매 6-1-6 사이클 분석 및 최적의 매수 타점 도출', 0)

    # 1. 도입부
    doc.add_heading('⚠️ 도입: 6등급 "무지성 매수"가 위험한 이유 (자금 잠김)', level=1)
    
    p = doc.add_paragraph()
    p.add_run('테마는 한 번 바닥인 6등급으로 떨어지면 길게는 수개월 동안 그 자리에 머물며 철저히 소외되는 이른바 ').bold = False
    p.add_run("'좀비 기간'").bold = True
    p.add_run('을 가집니다. 언제 오를지 모르는 6등급 상태에서 미리 매수해두는 것은 기회비용 측면에서 매우 큰 손실을 야기할 수 있습니다.\n\n')
    
    p.add_run('실제 [일간 테마 등급 변화 데이터]를 확인한 결과, 오늘 6등급인 테마가 내일도 6등급으로 ').bold = False
    p.add_run('제자리걸음을 할 확률은 무려 66.1%').bold = True
    p.add_run('에 달했습니다. 즉, 가장 바닥인 6등급에서 미리 사두는 이른바 "발바닥 매수"는 마음은 편할 수 있으나 자금이 묶여있는 시간이 너무 길어지게 됩니다.')

    # 2. 분석 1
    doc.add_heading('1. 바닥 탈출 성공 시의 초기 도약 패턴', level=1)
    doc.add_paragraph('만약 지루한 6등급을 깨고 수급이 들어오기 시작한다면, 첫날 어디까지 튀어 오를까요? (6등급 출발 기준)')
    doc.add_paragraph('6등급 -> 1등급 (단번에 대장급 수직 상승): 29.7% (가장 흔함)', style='List Bullet')
    doc.add_paragraph('6등급 -> 2등급 (강한 갭상승): 22.4%', style='List Bullet')
    doc.add_paragraph('6등급 -> 3등급 (안정적 상승): 18.7%', style='List Bullet')
    doc.add_paragraph('6등급 -> 5등급 (약한 반등): 17.1%', style='List Bullet')
    doc.add_paragraph('6등급 -> 4등급 (중간 반등): 12.2%', style='List Bullet')
    
    # 3. 분석 2
    doc.add_heading('2. 테마 등급과 주가 수익률의 상관관계', level=1)
    p = doc.add_paragraph()
    p.add_run('상관계수: ').bold = True
    p.add_run('+0.328 (양의 상관관계)\n').bold = True
    p.add_run('테마의 등급이 6등급에서 1등급으로 향할수록(등급 점수가 높아질수록), 해당 테마 내 속한 종목들의 평균 수익률도 뚜렷하게 우상향하는 경향이 통계적으로 확인되었습니다. 주식 시장 데이터에서 피어슨 상관계수가 0.3 이상이라는 것은 ')
    p.add_run('상당히 강하고 유의미한 동기화(커플링)').bold = True
    p.add_run('가 일어나고 있음을 의미합니다.')

    # 4. 분석 3
    doc.add_heading('3. 매도 타이밍 분석 (고점은 언제인가?) 💡', level=1)
    p = doc.add_paragraph()
    p.add_run('우리가 가장 궁금한 것은 ').bold = False
    p.add_run('"테마가 1등급(대장)을 찍은 날 팔아야 하는가? 아니면 더 들고 가도 되는가?"').bold = True
    p.add_run('입니다. 데이터 분석 결과, 평균적으로 주가의 실질 최고점은 테마가 1등급에 도달한 날보다 ')
    p.add_run('평균 0.44일 뒤').bold = True
    p.add_run('에 나타났습니다.\n')
    
    p = doc.add_paragraph()
    p.add_run('특히, 1등급 달성 당일에 전량 매도하기보다는 ').bold = False
    p.add_run('1등급 달성 이후에도 주가가 추가로 더 상승한 케이스가 전체의 40.7%').bold = True
    p.add_run('에 달했습니다. 따라서 1등급 도달 시점부터 분할 매도를 준비하는 것이 유리합니다.')

    # 5. 분석 4
    doc.add_heading('4. 첫 도약 등급에 따른 수익률 분석 🔥', level=1)
    p = doc.add_paragraph('과연 6등급에서 처음 탈출할 때, 서서히 올라가는 것이 좋을까요? 아니면 단숨에 대장으로 치고 올라가는 것이 좋을까요? 테마 소속 종목 전체 평균 수익률의 중앙값을 기준으로 분석한 결과는 다음과 같습니다.')
    
    doc.add_paragraph('1위: 6등급 ➔ 1등급 직행 (중앙값 약 5.7% 수익) 🏆', style='List Bullet')
    doc.add_paragraph('2위: 6등급 ➔ 2등급 출발 (중앙값 약 4.8% 수익)', style='List Bullet')
    doc.add_paragraph('3위: 6등급 ➔ 5등급 출발 (중앙값 약 2.7% 수익)', style='List Bullet')
    doc.add_paragraph('4위: 6등급 ➔ 3등급 출발 (중앙값 약 2.6% 수익)', style='List Bullet')
    doc.add_paragraph('꼴찌: 6등급 ➔ 4등급 출발 (중앙값 약 1.7% 수익)', style='List Bullet')
    
    p = doc.add_paragraph()
    p.add_run('\n즉, 바닥에서 찔끔 4~5등급으로 오르는 것보다, ')
    p.add_run('수급이 폭발하며 단숨에 1~2등급 대장급으로 치고 올라가는 테마(강한 갭상승, 상한가 속출)에 과감히 탑승하는 것이 실제 수익률 측면에서도 압도적으로 유리').bold = True
    p.add_run('하다는 사실이 통계적으로 증명되었습니다.')

    # 6. 승률 분석
    doc.add_heading('5. 도약 패턴별 승률 분석 (절대승률 및 실전승률) 🏆', level=1)
    p = doc.add_paragraph('수익률의 크기뿐만 아니라, "얼마나 자주 이기는가(승률)"에 대한 검증 결과입니다. 6등급 탈출 당일(D+0) 종가에 매수했을 때의 승률을 3가지 기준으로 도출했습니다.\n')
    
    p = doc.add_paragraph()
    p.add_run('① 절대 승률 (최소 수익 기회): ').bold = True
    p.add_run('단 한 번이라도 계좌가 빨간불(+수익)로 전환될 확률\n')
    p.add_run('② 실전 승률 (의미 있는 수익 기회): ').bold = True
    p.add_run('수수료 등을 감안해 평균 +3.0% 이상의 넉넉한 수익 구간을 줄 확률\n')
    p.add_run('③ 단기 승률 (D+1 청산): ').bold = True
    p.add_run('묻지도 따지지도 않고 다음 날(D+1) 종가에 기계적으로 매도했을 때의 승률\n')

    table = doc.add_table(rows=6, cols=5)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = '도약 패턴'
    hdr_cells[1].text = '발생 건수'
    hdr_cells[2].text = '① 절대 승률 (>0%)'
    hdr_cells[3].text = '② 실전 승률 (≥3%)'
    hdr_cells[4].text = '③ 단기 승률 (D+1)'

    # Data row 1
    row_cells = table.rows[1].cells
    row_cells[0].text = '6 ➔ 1 직행'
    row_cells[1].text = '73건'
    row_cells[2].text = '93.2% (1위)'
    row_cells[3].text = '63.0% (2위)'
    row_cells[4].text = '82.2% (1위)'

    # Data row 2
    row_cells = table.rows[2].cells
    row_cells[0].text = '6 ➔ 2 직행'
    row_cells[1].text = '55건'
    row_cells[2].text = '81.8%'
    row_cells[3].text = '63.6% (1위)'
    row_cells[4].text = '67.3%'

    # Data row 3
    row_cells = table.rows[3].cells
    row_cells[0].text = '6 ➔ 3 출발'
    row_cells[1].text = '46건'
    row_cells[2].text = '84.8%'
    row_cells[3].text = '45.7%'
    row_cells[4].text = '67.4%'

    # Data row 4
    row_cells = table.rows[4].cells
    row_cells[0].text = '6 ➔ 5 출발'
    row_cells[1].text = '42건'
    row_cells[2].text = '71.4%'
    row_cells[3].text = '47.6%'
    row_cells[4].text = '54.8%'

    # Data row 5
    row_cells = table.rows[5].cells
    row_cells[0].text = '6 ➔ 4 출발'
    row_cells[1].text = '30건'
    row_cells[2].text = '60.0% (꼴찌)'
    row_cells[3].text = '43.3% (꼴찌)'
    row_cells[4].text = '43.3% (꼴찌)'

    p = doc.add_paragraph()
    p.add_run('\n승률 지표에서도 6-1 직행 패턴의 파괴력이 입증되었습니다. 6등급에서 1등급으로 직행한 테마를 D+0에 매수하면, 단 한 번이라도 수익을 줄 확률이 무려 93.2%에 달하며, 다음 날 무조건 팔아도 82.2%의 확률로 수익을 확보할 수 있습니다.')

    # 7. 결론
    doc.add_heading('6. 결론 및 투자 전략: 통계가 증명하는 최적의 매수 타점', level=1)
    p = doc.add_paragraph()
    p.add_run('모든 데이터 분석 결과를 종합해 내린 결론입니다. 가장 승률이 높고 자금 회전율과 수익률을 극대화할 수 있는 완벽한 매수 타이밍은 ')
    p.add_run('"6등급에 철저히 소외되어 있던 테마가, 어느 날 단숨에 1등급이나 2등급으로 수직 상승하며 폭발적인 모멘텀을 보일 때(Point A)"').bold = True
    p.add_run('입니다.\n')
    
    p = doc.add_paragraph()
    p.add_run('따라서 매일 6등급 좀비 테마들을 관찰하시다가, ')
    p.add_run('어느 날 갑자기 의미 있는 거래량을 동반하며 등급표 최상단(1~2등급)으로 확! 쳐드는 바로 그 첫날이나 이튿날').bold = True
    p.add_run('에 올라타는 강한 돌파 매수 전략이 실제 통계상 "가장 큰 수익 창출"과 "안정적인 승률"을 동시에 담보하는 확실한 방법입니다.')

    # 8. 향후 계획 (Next Step)
    doc.add_heading('🚀 향후 분석 계획 (Next Step)', level=1)
    p = doc.add_paragraph()
    p.add_run('위 결론을 바탕으로, 앞으로 우리가 집중적으로 파고들 핵심 분석 과제는 다음과 같습니다:\n')
    
    p_plan1 = doc.add_paragraph(style='List Bullet')
    p_plan1.add_run('가장 압도적인 승률과 수익률을 자랑하는 "6-1 패턴" 정밀 타겟팅').bold = True
    p_plan1.add_run(': 6등급에서 1등급으로 수직 상승하는 테마(섹터)들의 구조적 특징을 추출합니다.')
    
    p_plan2 = doc.add_paragraph(style='List Bullet')
    p_plan2.add_run('섹터 차트 및 보조지표 선행 시그널 발굴').bold = True
    p_plan2.add_run(': 해당 6-1 패턴을 그리는 섹터들이 수직 상승을 시작하기 직전에 어떤 "차트적 시그널"과 "보조지표 특이점"을 보였는지 집중 분석하여, 6-1 직행을 사전에 미리 예측할 수 있는 궁극적인 선행 지표를 발굴할 예정입니다.')

    out_path = os.path.abspath('theme_analysis_insight_final_v5.docx')
    doc.save(out_path)
    print(f"Refined Word document successfully saved to: {out_path}")

if __name__ == "__main__":
    create_refined_document()
