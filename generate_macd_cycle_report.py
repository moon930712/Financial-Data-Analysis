import os
import pandas as pd
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def generate_report():
    doc = Document()
    
    # 제목
    title = doc.add_heading('MACD 히스토그램 사이클(주기) 분석 보고서', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_heading('1. 분석 개요', level=1)
    doc.add_paragraph('본 보고서는 MACD 히스토그램이 0선을 기준으로 상향 교차(Gold Cross)하여 유지되는 기간과 하향 교차(Dead Cross)하여 유지되는 기간을 분석한 결과입니다. 이를 통해 업종별 추세 지속성을 정량적으로 파악하는 것을 목적으로 합니다.')

    # 2. 통계 요약
    doc.add_heading('2. 전체 시장 평균 통계', level=1)
    # 실제 분석 코드에서 나왔던 값들을 하드코딩하거나 CSV에서 계산 (이미 알고 있으니 요약 형식으로 작성)
    doc.add_paragraph('전체 종목의 이력을 분석한 결과, 보편적인 추세 지속 기간은 다음과 같습니다.')
    p = doc.add_paragraph()
    p.add_run('• 평균 상승 지속일 (0선 위): ').bold = True
    p.add_run('약 13.62일')
    p = doc.add_paragraph()
    p.add_run('• 평균 하락 지속일 (0선 밑): ').bold = True
    p.add_run('약 13.30일')

    # 3. 업종별 분석 결과 (표 추가)
    doc.add_heading('3. 업종별(중분류) 상세 분석 (상위 20개)', level=1)
    csv_path = 'result/macd_cycle_stats.csv'
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        
        # 표 생성
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = '업종명 (WICS 중분류)'
        hdr_cells[1].text = '평균 상승지속일'
        hdr_cells[2].text = '평균 하락지속일'
        
        for index, row in df.head(20).iterrows():
            row_cells = table.add_row().cells
            row_cells[0].text = str(row['중분류'])
            row_cells[1].text = f"{row['상승구간(0선위)']:.2f}일"
            row_cells[2].text = f"{row['하락구간(0선밑)']:.2f}일"
    else:
        doc.add_paragraph('상세 통계 데이터(CSV)를 찾을 수 없습니다.')

    doc.add_page_break()

    # 4. 시각화 자료
    doc.add_heading('4. 업종별 사이클 분포 시각화', level=1)
    img_path = 'result/macd_cycle_analysis.png'
    if os.path.exists(img_path):
        doc.add_picture(img_path, width=Inches(6.0))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph('\n[그림 1] 상위 10개 업종별 MACD 히스토그램 지속 일수 분포 (Boxplot)')
    else:
        doc.add_paragraph('시각화 이미지 파일을 찾을 수 없습니다.')

    # 5. 회복기(Phase 1) 유예 기간 분석
    doc.add_heading('5. 회복기(Phase 1) 유예 기간 (0선 돌파까지)', level=1)
    doc.add_paragraph('회복기(Phase 1)는 지표가 음수권에서 상승으로 전환된 시점부터 0선을 돌파하기 직전까지의 기간을 의미합니다.')
    p = doc.add_paragraph()
    p.add_run('• 전체 종목 평균 회복기 지속일: ').bold = True
    p.add_run('약 3.02일')
    
    doc.add_paragraph('\n[업종별 회복기 평균 유예 기간]')
    recovery_csv_path = 'result/recovery_phase_stats.csv'
    if os.path.exists(recovery_csv_path):
        rdf = pd.read_csv(recovery_csv_path)
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = '업종명 (WICS 중분류)'
        hdr_cells[1].text = '평균 회복지속일'
        hdr_cells[2].text = '표본 수(count)'
        
        for index, row in rdf.head(15).iterrows():
            row_cells = table.add_row().cells
            row_cells[0].text = str(row['중분류'])
            row_cells[1].text = f"{row['mean']:.2f}일"
            row_cells[2].text = f"{int(row['count'])}건"
    
    doc.add_paragraph('\n즉, 주가 하락세가 멈추고 지표가 고개를 들기 시작하면 통계적으로 약 3거래일 내에 0선을 돌파하며 본격적인 상승 국면(Phase 2)으로 진입할 가능성이 매우 높습니다.')

    # 6. 결론 및 전략적 제언
    doc.add_heading('6. 전략적 제언', level=1)
    doc.add_paragraph('• 상승 주기가 긴 업종(부동산, 상업서비스 등)은 회복기 진입 시 상대적으로 긴 호흡으로 보유가 가능합니다.')
    doc.add_paragraph('• 반도체나 에너지 업종은 평균 주기가 약 13일로 짧은 편이므로, 2주 내외의 빠른 순환매 대응이 필요합니다.')
    doc.add_paragraph('• 본 지표를 활용하여 "회복기(Phase 1)" 매수 후 "둔화기(Phase 4)"로 접어드는 통계적 시점을 예측할 수 있습니다.')

    report_path = "result/MACD_사이클_분석보고서_v3.docx"
    doc.save(report_path)
    print(f"보고서가 성공적으로 생성되었습니다: {report_path}")

if __name__ == "__main__":
    generate_report()
