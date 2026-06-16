# -*- coding: utf-8 -*-
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
import os

def create_word_document():
    doc = Document()

    # Set default font
    style = doc.styles['Normal']
    style.font.name = 'Malgun Gothic'
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Malgun Gothic')
    style.font.size = Pt(11)

    # Add title
    title = doc.add_heading('테마 6-1-6 사이클 분석 결과 및 투자 인사이트', 0)
    
    # Add content
    doc.add_heading('1. 등급 상승 패턴 분포 (6등급 출발 기준)', level=1)
    doc.add_paragraph('6등급 -> 1등급 (단번에 대장급 수직 상승): 29.7% (가장 흔함!)', style='List Bullet')
    doc.add_paragraph('6등급 -> 2등급 (강한 갭상승): 22.4%', style='List Bullet')
    doc.add_paragraph('6등급 -> 3등급 (안정적 상승): 18.7%', style='List Bullet')
    doc.add_paragraph('6등급 -> 5등급 (약한 반등): 17.1%', style='List Bullet')
    doc.add_paragraph('6등급 -> 4등급 (중간 반등): 12.2%', style='List Bullet')

    doc.add_heading('2. 주가 수익률과의 상관관계', level=1)
    p = doc.add_paragraph()
    p.add_run('상관계수: ').bold = True
    p.add_run('+0.328 (양의 상관관계)\n').bold = True
    p.add_run('등급이 6등급에서 1등급으로 향할수록(점수가 높아질수록), 해당 테마 내 종목들의 평균 수익률도 뚜렷하게 우상향하는 경향이 확인되었습니다. 주식 시장 데이터에서 0.3 이상이면 ')
    p.add_run('상당히 강하고 유의미한 동기화(커플링)').bold = True
    p.add_run('이 일어나고 있음을 의미합니다.')

    doc.add_heading('3. 고점 타이밍 분석 (가장 중요한 인사이트 💡)', level=1)
    p = doc.add_paragraph()
    p.add_run('우리가 가장 궁금한 것은 ').bold = False
    p.add_run('"테마가 1등급(대장)을 찍은 날 팔아야 하는가? 아니면 더 들고 가도 되는가?"').bold = True
    p.add_run('입니다. 분석 결과, 평균적으로 주가의 최고점은 테마가 1등급에 도달한 날보다 ')
    p.add_run('평균 0.44일 뒤에 나타났습니다.\n\n').bold = True
    p.add_run('1등급 달성 이후에도 주가가 추가로 더 상승함 (40.7%) 🔥').bold = True

    doc.add_heading('4. 첫 반등 강도에 따른 실질 수익률 비교 (핵심 발견!!)', level=1)
    p = doc.add_paragraph()
    p.add_run('놀랍게도 6등급에서 1등급으로 "단번에" 오르는 비율이 가장 흔하지만(29.7%), 실질적인 수익률(중앙값 기준)은 정반대의 결과를 보여주었습니다.\n\n')
    
    doc.add_paragraph('6등급 -> 4등급 출발 (중간 반등): 실질 최고수익률 1위 🏆', style='List Bullet')
    doc.add_paragraph('6등급 -> 5등급 출발 (약한 반등): 실질 최고수익률 2위', style='List Bullet')
    doc.add_paragraph('...', style='List Bullet')
    doc.add_paragraph('6등급 -> 1등급 출발 (단숨에 대장): 실질 최고수익률 꼴찌 (4/5등급 출발 대비 반토막)', style='List Bullet')
    
    p = doc.add_paragraph()
    p.add_run('\n이러한 결과가 나오는 이유는 명확합니다. 단숨에 1등급으로 점프하는 경우는 대형 호재나 갭상승으로 인해 "이미 오를 대로 오른 채" 시작하기 때문에, 막상 탑승하고 난 이후의 추가 상승 여력이 가장 적습니다.\n반면, 6등급에서 4등급이나 5등급으로 서서히 고개를 들며 출발하는 테마는 ')
    p.add_run('"진짜 상승의 초입(무릎)"').bold = True
    p.add_run('에 해당하므로, 1등급 대장주가 되기까지의 모든 상승 분을 고스란히 수익으로 흡수할 수 있습니다.')

    doc.add_heading('5. 투자 전략: 최적의 매수 타점', level=1)
    p = doc.add_paragraph()
    p.add_run('데이터 분석 결과를 종합해 보았을 때, ')
    p.add_run('"무작정 6등급일 때 매수하는 것"은 자금이 오래 묶일 수 있는 \'양날의 검\'').bold = True
    p.add_run('입니다.\n결론부터 말씀드리면 가장 승률이 높고 효율적인 매수 타이밍은 ')
    p.add_run('"6등급에 머물던 테마가 5등급이나 4등급으로 갓 고개를 들며 상승 전환(Point A)을 확정 지었을 때"').bold = True
    p.add_run('입니다. (이른바 무릎에서 사는 전략)\n그 이유는 우리가 방금 뽑아본 데이터들에 명확히 나타나 있습니다.')

    doc.add_heading('⚠️ 6등급 무지성 매수가 위험한 이유 (자금 잠김)', level=2)
    p = doc.add_paragraph()
    p.add_run('테마는 한 번 6등급으로 떨어지면 길게는 수개월 동안 그 자리에 머물며 소외되는 이른바 ')
    p.add_run("'좀비 기간'").bold = True
    p.add_run('을 가집니다. 언제 오를지 모르는 6등급 상태에서 매수하면, 기회비용이 크게 날아갈 수 있습니다.\n앞서 확인한 [일간 변화 데이터]에 따르면, ')
    p.add_run('6등급 -> 6등급으로 매일 제자리걸음을 할 확률이 무려 66.1%').bold = True
    p.add_run('에 달했습니다. 즉, 6등급에서 사면 내일도 모레도 계속 6등급일 확률이 압도적으로 높습니다.')

    doc.add_heading('💡 통계가 말해주는 최적의 매수 타점 (확인 매수)', level=2)
    p = doc.add_paragraph()
    p.add_run('하지만 6등급에 있던 테마가 ')
    p.add_run('5등급이나 4등급으로 한두 계단 올라서는 순간(바닥 탈출)').bold = True
    p.add_run('을 포착한다면 이야기가 달라집니다.\n앞선 데이터에서 성공적으로 1등급까지 도달한 대장 테마들은 바닥을 탈출할 때 찔끔 오르지 않고, 단숨에 1~2등급으로 수직 상승(52%)하거나 최소 3~4등급으로 강하게 치고 올라오는(30%) 특징을 보였습니다.\n따라서 매일 6등급 테마들을 관찰하시다가, 어느 날 갑자기 6등급에서 4등급 이상으로 확 튀어 오르면서 MACD 바닥(Point A)을 형성하는 테마가 나타난다면, 그때가 바로 수급이 본격적으로 들어왔음을 알리는 ')
    p.add_run('강력한 매수 타이밍(급소)').bold = True
    p.add_run('입니다.')

    p = doc.add_paragraph()
    p.add_run('요약하자면: ').bold = True
    p.add_run('가장 바닥인 6등급에서 미리 사두는 것(발바닥 매수)은 마음은 편할 수 있으나 시간이 너무 오래 걸립니다. 대신, 6등급에 웅크리고 있던 테마가 ')
    p.add_run('의미 있는 거래량을 동반하며 4~5등급 위로 고개를 탁! 쳐드는 바로 그 첫날이나 이튿날(무릎 매수)').bold = True
    p.add_run('에 올라타는 것이 실제 통계상 "가장 큰 수익률(실질 최고수익 1위)"과 "빠른 자금 회전율"을 동시에 극대화하는 방법입니다!')

    out_path = os.path.abspath('theme_analysis_insight_v2.docx')
    doc.save(out_path)
    print(f"Word document successfully saved to: {out_path}")

if __name__ == "__main__":
    create_word_document()
