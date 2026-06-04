import docx

try:
    doc = docx.Document('Sector_Rotation_Midterm_Report_v2.docx')

    sec2_para = None
    for p in doc.paragraphs:
        if p.text.startswith('2. 다양한 관점의 테마 순환 분석'):
            sec2_para = p
            break
            
    if sec2_para is not None:
        p_sub = sec2_para.insert_paragraph_before()
        run = p_sub.add_run('[통계적 왜곡(아웃라이어) 제거 방법론: IQR(사분위수 범위) 방식 적용]')
        run.bold = True
        
        sec2_para.insert_paragraph_before('본 백테스팅에서는 \'평균의 함정\'을 유발하는 극단적 급등락 종목(예: 어쩌다 한 번 터지는 +200% 수익 종목)을 걸러내어 \'진짜 평균\'을 구하기 위해 IQR(Interquartile Range) 방식을 적용했습니다. 각 국면별 수익률 데이터에서 하위 25%(Q1)와 상위 25%(Q3)의 값을 구한 뒤, 그 간격(IQR = Q3 - Q1)을 기준으로 \'Q1 - 1.5 * IQR\' 보다 낮거나 \'Q3 + 1.5 * IQR\' 보다 높은 비정상적인 꼬리 값(극단값)들을 모두 삭제하였습니다. 이를 통해 소수의 대박 종목이 전체 평균을 끌어올리는 착시 현상을 완벽하게 차단하고, 가장 보수적이고 신뢰할 수 있는 수익률 수치를 도출했습니다.')
        sec2_para.insert_paragraph_before('')

    doc.save('Sector_Rotation_Midterm_Report_v3.docx')
    print("Report updated successfully to v3.")

except Exception as e:
    import traceback
    traceback.print_exc()
