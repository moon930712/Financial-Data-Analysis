import docx

try:
    doc = docx.Document('Sector_Rotation_Midterm_Report.docx')

    # Update Section 3.2
    found_32 = False
    for p in doc.paragraphs:
        if '3.2. 보유 기간별' in p.text:
            found_32 = True
        elif found_32 and '5일 보유:' in p.text:
            p.text = '• 5일 보유: 평균 0.95% / 중앙값 1.40% / 승률 57.3% (시세 분출에 필요한 턴어라운드 시간 부족)'
        elif found_32 and '8일 보유:' in p.text:
            p.text = '• 8일 보유: 평균 3.42% / 중앙값 2.76% / 승률 62.0% (본격적인 상승 궤도 진입)'
        elif found_32 and '14일 보유:' in p.text:
            p.text = '• 14일 보유: 평균 5.76% / 중앙값 4.09% / 승률 63.2% (수익률 폭발적 극대화)'
        elif found_32 and p.text.startswith('결론적으로'):
            break

    # Rename Section 4 to 5
    sec5_para = None
    for p in doc.paragraphs:
        if p.text.startswith('4. 결론 및 향후 과제'):
            p.text = p.text.replace('4. 결론', '5. 결론')
            sec5_para = p
            break

    if sec5_para is not None:
        # Insert new Section 4 heading and text
        h4 = sec5_para.insert_paragraph_before('4. 중하위(61~100위) -> 최상위 진입 섹터의 국면별 수익률 (14일 보유)', style='Heading 1')
        p4 = sec5_para.insert_paragraph_before('가장 극적인 순위 상승(Jump)을 보여준 테마(61~100위 → 1~10위)를 대상으로 14일간 보유했을 때의 국면별 수익률을 추가 분석했습니다. 아웃라이어를 제거한 결과, 2국면(눌림목) 종목을 잡았을 때 무려 10%가 넘는 중앙값 수익률과 76%대의 경이적인 승률이 달성되었습니다.')
        
        # Create table at the end of the document
        table = doc.add_table(rows=5, cols=5)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = '국면 (Phase)'
        hdr[1].text = '평균 수익률'
        hdr[2].text = '중앙값 (Median)'
        hdr[3].text = '승률 (Win Rate)'
        hdr[4].text = '표본 수'
        
        data = [
            ('1국면 (바닥 탈출)', '2.85%', '2.62%', '57.5%', '362'),
            ('2국면 (하락 지속)', '13.00% (가장 높음)', '10.13% (가장 높음)', '76.8%', '82'),
            ('3국면 (상승 추세)', '4.39%', '2.28%', '57.8%', '258'),
            ('4국면 (상승 둔화)', '8.74%', '6.14%', '67.3%', '52')
        ]
        
        for i, row_data in enumerate(data):
            cells = table.rows[i+1].cells
            for j, val in enumerate(row_data):
                cells[j].text = val
                
        # Move the table before sec5_para
        sec5_para._element.addprevious(table._element)
        
        # Insert a blank paragraph after the table for spacing
        sec5_para.insert_paragraph_before('')

    doc.save('Sector_Rotation_Midterm_Report_v2.docx')
    print("Report updated successfully.")

except Exception as e:
    import traceback
    traceback.print_exc()
