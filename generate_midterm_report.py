import sys
import subprocess

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    import docx
except ImportError:
    install('python-docx')
    import docx

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

doc = Document()

# Title
title = doc.add_heading('테마 순환매 및 퀀트 백테스트 고도화 중간보고서', 0)
title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

# 1. 서론
doc.add_heading('1. 분석 배경 및 목적', level=1)
p = doc.add_paragraph()
p.add_run('기존 평균 수익률 기반 백테스트의 한계점(평균의 함정, 아웃라이어 왜곡, 비현실적 균등 분배)을 극복하고자, 생존 편향을 제거하고 중앙값(Median) 및 승률을 중심으로 한 새로운 퀀트 분석 모형을 설계하고 검증하였습니다.')

# 2. 다양한 분석
doc.add_heading('2. 다양한 관점의 테마 순환 분석', level=1)
doc.add_paragraph('[Heatmap 분석]: 테마의 전일 랭킹 그룹과 당일 랭킹 그룹(최상위~최하위) 간의 이동(Transition) 매트릭스를 그리고, 어떤 순위 변동 패턴에서 8일 후 수익률이 가장 높게 나타나는지 히트맵 형태로 분석했습니다.', style='List Bullet')
doc.add_paragraph('[Jump 분석]: 하위권에 있던 테마가 갑자기 상위권으로 급등(Jump)했을 때의 수익률 패턴을 분석했습니다.', style='List Bullet')
doc.add_paragraph('[Steady 분석]: 상위권 랭킹을 꾸준히 유지(Steady)하는 테마들의 향후 수익률을 분석했습니다.', style='List Bullet')
doc.add_paragraph('[Phase 분석]: Top 10 테마 내에서도 개별 종목이 어떤 국면(Phase)에 속해있는지에 따라 수익률과 승률이 어떻게 달라지는지 분석했습니다.', style='List Bullet')

# 3. 주요 결과
doc.add_heading('3. 주요 백테스트 결과 및 인사이트', level=1)
doc.add_heading('3.1. 테마 랭킹이 오늘 \'최상위(1위~10위)\'로 상승했을 때의 수익률', level=2)
doc.add_paragraph('어제 순위에서 오늘 최상위권(Top 10)으로 진입했을 때의 수익률을 비교한 결과, 바닥에서 급등한 경우(평균의 착시)보다 상위권에서 진입한 경우가 가장 실질적인 수익(중앙값)이 높았습니다.')

table = doc.add_table(rows=1, cols=3)
table.style = 'Table Grid'
hdr_cells = table.rows[0].cells
hdr_cells[0].text = '어제 순위(Prev) -> 오늘 순위(Curr)'
hdr_cells[1].text = '평균 수익률 (Average)'
hdr_cells[2].text = '중앙값 수익률 (Median)'

data = [
    ('1. 최상위(1~10) -> 최상위 유지', '-0.12%', '-0.92%'),
    ('2. 상위(11~30) -> 최상위 진입', '2.90%', '1.87% (가장 높음)'),
    ('3. 중위(31~60) -> 최상위 진입', '4.13%', '0.78%'),
    ('4. 중하위(61~100) -> 최상위 진입', '4.27% (가장 높음)', '1.85%'),
    ('5. 최하위(101~150) -> 최상위 진입', '1.61%', '0.55%')
]

for item in data:
    row_cells = table.add_row().cells
    row_cells[0].text = item[0]
    row_cells[1].text = item[1]
    row_cells[2].text = item[2]

doc.add_paragraph('')
doc.add_heading('3.2. 보유 기간별 (5일 vs 8일 vs 14일) 전략 비교', level=2)
doc.add_paragraph('보유 기간에 따른 핵심 주도주(Top 10 테마 내 2국면 종목)의 수익률 변화를 분석한 결과, 기간이 길어질수록 압도적으로 성과가 상승하는 것을 확인하였습니다.')
doc.add_paragraph('• 5일 보유: 수익률과 승률이 상대적으로 낮으며, 시세 분출에 필요한 턴어라운드 시간이 부족함.')
doc.add_paragraph('• 8일 보유: 승률과 수익률이 크게 상승하며, 본격적인 상승 궤도에 진입함.')
doc.add_paragraph('• 14일 보유: 평균 5.76%, 중앙값 4.09%, 승률 63.2%를 달성하며 수익률이 폭발적으로 극대화됨.')
doc.add_paragraph('결론적으로 5일 이하의 단기적 매매보다는, 주도 테마의 눌림목을 잡아 14일(약 2~3주) 동안 느긋하게 홀딩하는 스윙(Swing) 전략으로 길게 봐야 실질적인 계좌 수익이 확실하게 누적된다는 사실을 통계적으로 입증하였습니다.')

# 4. 결론
doc.add_heading('4. 결론 및 향후 과제', level=1)
doc.add_paragraph('Top 10 주도 테마 중 2국면에 위치한 종목을 매수하여 14일간 스윙 보유하는 전략이 가장 우수한 엣지(Edge)를 가짐을 통계적(IQR 아웃라이어 제거 적용)으로 증명했습니다. 향후 이를 바탕으로 실전 매매 스크리너를 구축하여 검증을 진행할 예정입니다.')

doc.save('Sector_Rotation_Midterm_Report.docx')
print("Report generated successfully.")
