import os
import requests

def load_env(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

load_env('.env')
NOTION_TOKEN = os.environ.get('NOTION_API_KEY')
PAGE_ID = "33b99b3125fc803c8482d822844f9a81"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28"
}

url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
res = requests.get(url, headers=headers)
if res.status_code == 200:
    blocks = res.json().get('results', [])
    for b in blocks:
        if b['type'] == 'child_database':
            print(f"Found Database! Title: {b['child_database']['title']}, ID: {b['id']}")
            
            # Let's write this DATABASE ID to notion_daily_logger.py
            db_id = b['id'].replace("-", "")
            with open('src/notion_daily_logger.py', 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace('DATABASE_ID = "YOUR_DATABASE_ID_HERE"', f'DATABASE_ID = "{db_id}"')
            with open('src/notion_daily_logger.py', 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated src/notion_daily_logger.py with Database ID: {db_id}")
            break
    else:
        print("No child database found on this page.")
else:
    print(f"Error checking page: {res.status_code} - {res.text}")
