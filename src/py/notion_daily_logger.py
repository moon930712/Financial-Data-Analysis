import os
import requests
import argparse
from datetime import datetime

def load_env(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

load_env('../.env')
load_env('.env')

NOTION_TOKEN = os.environ.get('NOTION_API_KEY')
# 달력 형태의 데이터베이스 ID를 이곳에 적습니다! (기존 Page ID와 다름)
DATABASE_ID = "33b99b3125fc80fd85c8ca28ddfe233c"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def create_daily_log(title, content, date=None):
    if not NOTION_TOKEN or DATABASE_ID == "YOUR_DATABASE_ID_HERE":
        print("Error: Please set NOTION_API_KEY in .env and update DATABASE_ID in script.")
        return

    today_str = date if date else datetime.now().strftime('%Y-%m-%d')
    url = "https://api.notion.com/v1/pages"

    # 노션 데이터베이스 스키마 구조
    # 기본적으로 '이름' (title)과 '날짜' (date) 컬럼이 있다고 가정합니다.
    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "이름": {
                "title": [{"text": {"content": title}}]
            },
            "날짜": {
                "date": {"start": today_str}
            }
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            }
        ]
    }

    print(f"Creating Daily Log in Notion for {today_str}...")
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"[성공] {today_str} 날짜로 업무 정리가 노션에 기록되었습니다!")
    else:
        print(f"[실패] 노션 API 에러 ({response.status_code}): {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Notion Daily Logger")
    parser.add_argument("--title", type=str, default="오늘의 퀀트 스크리닝 개발 및 정리", help="Log Title")
    parser.add_argument("--content", type=str, default="내용을 입력하세요.", help="Detailed content")
    parser.add_argument("--date", type=str, default=None, help="Log Date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    create_daily_log(args.title, args.content, args.date)
