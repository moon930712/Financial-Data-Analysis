import os
import json
import requests
import pandas as pd
from datetime import datetime

def load_env(filepath):
    """ .env 파일에서 환경변수 로드 """
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('../.env')  # src/ 내부에 있으므로 상위 디렉토리 참조
load_env('.env')     # 혹은 루트에서 실행될 경우

NOTION_TOKEN = os.environ.get('NOTION_API_KEY')
PAGE_ID = "320802bfab6b434a9f4ea8cfe48eaa0a"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def sync_report_to_notion():
    if not NOTION_TOKEN:
        print("Error: NOTION_API_KEY is not defined in .env")
        return

    # 1. 아까 뽑아둔 결과값 CSV 읽기
    results_path = 'results/industry_zscore_ranking.csv'
    if not os.path.exists(results_path):
        results_path = '../results/industry_zscore_ranking.csv'
        
    try:
        df = pd.read_csv(results_path, encoding='utf-8-sig')
    except FileNotFoundError:
        print("Error: Could not find ranking CSV. Run quant screener first.")
        return

    # Top 3 업종 변수에 저장
    top_industries = df.head(3)
    
    # 노션 페이지에 추가할 블록들 (Blocks) 구성
    today_str = datetime.now().strftime('%Y-%m-%d')
    children_blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": f"📊 {today_str} 업종별 퀀트 랭킹 (Z-Score)"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "과거 3년치 펀더멘탈 시계열 데이터를 바탕으로 가치(Value), 밀집도(Density), 파생 수익성(Fundamental)을 다중 결합하여 산출한 오늘의 투자 전략 랭킹입니다."}}
                ]
            }
        }
    ]

    # 각 순위별로 텍스트 생성해서 블록에 넣기
    for i, row in top_industries.iterrows():
        rank = i + 1
        industry_name = row['industry']
        z_score = row['total_z_score']
        density = row['undervalue_density']
        
        block = {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"{rank}위: "}},
                    {"type": "text", "text": {"content": f"{industry_name} ", "link": None}, "annotations": {"bold": True, "color": "blue_background"}},
                    {"type": "text", "text": {"content": f"(Total Z-Score: {z_score:.2f} / 극저평가 밀집도: {density:.1f}%)"}}
                ]
            }
        }
        children_blocks.append(block)

    # 깃허브 링크 블록 추가
    github_block = {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [
                {"type": "text", "text": {"content": "💻 상세 데이터 추출 로직 및 파이썬 쿼리 원본은 "}},
                {"type": "text", "text": {"content": "[GitHub Repository]", "link": {"url": "https://github.com/moon930712/Financial-Data-Analysis/tree/main/src"}}},
                {"type": "text", "text": {"content": " 에서 투명하게 공개하고 관리 중입니다."}}
            ],
            "icon": {"type": "emoji", "emoji": "📁"},
            "color": "gray_background"
        }
    }
    children_blocks.append(github_block)
    
    # 구분선 추가
    children_blocks.append({"object": "block", "type": "divider", "divider": {}})

    # Notion API 호출: 해당 Page의 자식(children) 요소로 위 블록들을 통째로 덧붙이기 (Append)
    url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
    payload = {"children": children_blocks}

    print(f"Sending data to Notion Page ID: {PAGE_ID} ...")
    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print("[성공] 노션에 퀀트 요약 리포트와 깃허브 링크가 완벽하게 전송되었습니다!")
    else:
        print(f"[실패] 노션 API 에러 ({response.status_code}): {response.text}")

if __name__ == "__main__":
    sync_report_to_notion()
