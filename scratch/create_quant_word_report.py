import os
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

def create_quant_report():
    doc = Document()
    
    # 1. 문서 제목
    title = doc.add_heading('테마 순환매 패턴 퀀트 분석 리포트', 0)
    title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    
    subtitle = doc.add_paragraph('상위 10개 패턴 성과 및 리스크 집중 분석')
    subtitle.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    
    doc.add_heading('1. 분석 개요 및 상위 10개 패턴', level=1)
    doc.add_paragraph(
        '과거 1.5년 데이터를 바탕으로 발생 빈도(Count)와 D+5 수익 마감 확률(Win Rate)이 가장 높은 '
        '상위 10개 패턴을 추출하였습니다. 대상 패턴은 다음과 같습니다.'
    )
    
    patterns = [
        '4등급 -> 4등급 -> 4등급', '3등급 -> 3등급 -> 3등급', '6등급 -> 4등급 -> 1등급',
        '4등급 -> 3등급 -> 1등급', '2등급 -> 4등급 -> 1등급', '2등급 -> 5등급 -> 5등급',
        '4등급 -> 2등급 -> 2등급', '4등급 -> 4등급 -> 6등급', '5등급 -> 5등급 -> 5등급',
        '5등급 -> 2등급 -> 2등급'
    ]
    for p in patterns:
        doc.add_paragraph(f'• {p}', style='List Bullet')
        
    doc.add_heading('2. 수익률 우수 및 안정 패턴 분석', level=1)
    doc.add_paragraph(
        '해당 패턴들의 진입 후 다음 등급 전이 확률 및 5일간의 누적 수익률(평균 및 중앙값)을 '
        '확인한 결과, 다음 세 가지 패턴이 전체적으로 가장 우수한 성과를 기록했습니다.'
    )
    
    doc.add_heading('① 4등급 -> 3등급 -> 1등급 (최고 기대 성과 + 안정적 패턴)', level=2)
    doc.add_paragraph('• 특징: 안정적으로 우상향하는 강력한 모멘텀을 지닌 최선호 패턴입니다.')
    doc.add_paragraph('• 리스크 검증 데이터:')
    p = doc.add_paragraph()
    p.add_run('  - 표준편차 (변동성): 5.17%\n')
    p.add_run('  - 최대 수익률 (Max): 22.39% / 최소 수익률 (Min): -10.02%\n')
    p.add_run('  - 5% 이상 큰 손실을 입을 확률: 6.80% (도박성 패턴의 절반 이하)')
    
    doc.add_heading('② 6등급 -> 4등급 -> 1등급 (강력한 V자 반등형)', level=2)
    doc.add_paragraph('• 특징: 최하위 6등급에서 1등급으로 급반등하며 높은 수익률을 기록하는 패턴입니다.')
    
    doc.add_heading('③ 4등급 -> 2등급 -> 2등급 (극단적 안정 추종형)', level=2)
    doc.add_paragraph('• 특징: 상위 패턴 중 변동성이 가장 낮아 손실 위험이 적고 안정적인 패턴입니다.')
    doc.add_paragraph('• 리스크 검증 데이터:')
    p = doc.add_paragraph()
    p.add_run('  - 표준편차 (변동성): 4.19% (가장 낮음)\n')
    p.add_run('  - 최대 수익률 (Max): 15.69% / 최소 수익률 (Min): -15.54%\n')
    p.add_run('  - 5% 이상 큰 손실을 입을 확률: 6.67%')
    
    doc.add_heading('3. 투기적/도박적 패턴 경고 (평균의 착시)', level=1)
    doc.add_heading('① 2등급 -> 5등급 -> 5등급', level=2)
    doc.add_paragraph(
        '평균 수익률은 우수해 보이지만, 실제 분포를 확인하면 수익이 나는 비율이 너무 적고 '
        '오히려 마이너스가 나는 비율이 훨씬 높아 매우 도박적인 패턴을 보입니다.'
    )
    doc.add_paragraph('• 리스크 검증 데이터:')
    p = doc.add_paragraph()
    p.add_run('  - 표준편차 (변동성): 7.02% (상위 패턴 중 최고 수준)\n')
    p.add_run('  - 최대 수익률 (Max): 47.93% (극단적인 대박 발생)\n')
    p.add_run('  - 최소 수익률 (Min): -15.00% (큰 폭의 손실)\n')
    p.add_run('  - 5% 이상 큰 손실을 입을 확률: 14.85% (안정적 패턴 대비 2배 이상의 깡통 위험)')
    doc.add_paragraph(
        '결론적으로 극단적인 대박 수익률(47.93%) 몇 개가 평균을 높여놓은 전형적인 "평균의 함정" 패턴입니다.'
    )
    
    doc.add_heading('4. 최적 청산 시점 (Optimal Exit Timing) 가이드', level=1)
    doc.add_paragraph(
        '진입 후 D+1 ~ D+5 중 어느 날짜에 수익률 중앙값이 극대화되는지 분석하여 '
        '최적의 매도 시점을 제안합니다.'
    )
    
    doc.add_heading('① 4등급 -> 3등급 -> 1등급', level=2)
    doc.add_paragraph('• 일별 누적 수익률 추이: D+1(0.07%) → D+2(0.42%) → D+3(0.77%) → D+4(1.16%) → D+5(1.61%)')
    doc.add_paragraph('• 가이드: 보유 기간 동안 꾸준히 우상향하므로, D+5일까지 가득 채워 보유하는 것이 가장 유리합니다.')
    
    doc.add_heading('② 6등급 -> 4등급 -> 1등급', level=2)
    doc.add_paragraph('• 일별 누적 수익률 추이: D+1(-0.07%) → D+2(0.22%) → D+3(0.77%) → D+4(0.67% - 일시조정) → D+5(1.38%)')
    doc.add_paragraph('• 가이드: 중간 D+4일에 조정을 겪지만 최종일에 급등하므로, 중간 흔들림에 털리지 않고 D+5일까지 인내하는 전략이 필요합니다.')
    
    output_path = '테마_순환매_패턴_퀀트분석_리포트.docx'
    doc.save(output_path)
    print(f"Report saved to {output_path}")

if __name__ == '__main__':
    create_quant_report()
