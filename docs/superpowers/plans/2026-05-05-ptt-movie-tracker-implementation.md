# PTT 電影版「好雷/普雷」追蹤器實作計劃

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天定時爬取 PTT Movie 版，篩選「好雷」與「普雷」文章並推送到 Discord，同時避免重複通知。

**Architecture:** 使用 Python `requests` 與 `BeautifulSoup` 進行網頁爬取，透過 Discord Webhook 發送訊息。利用 GitHub Actions 進行每日排程，並透過 GitHub Actions Cache 保存已發送過的文章紀錄。

**Tech Stack:** Python 3.10+, requests, beautifulsoup4, GitHub Actions.

---

### Task 1: 專案基礎環境設定

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`

- [ ] **Step 1: 建立 `requirements.txt`**

```text
requests==2.31.0
beautifulsoup4==4.12.3
```

- [ ] **Step 2: 建立 `.gitignore`**

```text
__pycache__/
*.py[cod]
.env
sent_articles.txt
```

- [ ] **Step 3: 提交變更**

```bash
git add requirements.txt .gitignore
git commit -m "chore: initial project setup"
```

---

### Task 2: 撰寫核心爬蟲邏輯 (PTT 抓取)

**Files:**
- Create: `scraper.py`

- [ ] **Step 1: 撰寫 `scraper.py` 中的 PTT 爬取函式**

```python
import requests
from bs4 import BeautifulSoup
import time

def get_ptt_articles(pages=6):
    base_url = "https://www.ptt.cc"
    url = f"{base_url}/bbs/movie/index.html"
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": "over18=1"}
    all_articles = []

    for _ in range(pages):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 抓取文章列表
            for entry in soup.select(".r-ent"):
                title_tag = entry.select_one(".title a")
                if title_tag:
                    title = title_tag.text
                    link = base_url + title_tag["href"]
                    # 篩選標題
                    if "好雷" in title or "普雷" in title:
                        all_articles.append({"title": title, "link": link})
            
            # 尋找上一頁連結
            prev_link = soup.select(".btn-group-paging a")[1]
            if prev_link and "href" in prev_link.attrs:
                url = base_url + prev_link["href"]
            else:
                break
            time.sleep(0.5) # 稍微延遲避免被封 IP
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            break
            
    return all_articles

if __name__ == "__main__":
    articles = get_ptt_articles()
    print(f"Found {len(articles)} articles.")
    for a in articles[:3]:
        print(f"- {a['title']}")
```

- [ ] **Step 2: 執行腳本驗證爬蟲是否能正常抓取**

Run: `python3 scraper.py`
Expected: 輸出抓取到的文章數量與前三標題（確認標題含有好雷/普雷）。

- [ ] **Step 3: 提交變更**

```bash
git add scraper.py
git commit -m "feat: implement ptt scraper logic"
```

---

### Task 3: 實作重複過濾與 Discord 發送

**Files:**
- Modify: `scraper.py`

- [ ] **Step 1: 更新 `scraper.py` 增加過濾與 Discord 發送邏輯**

```python
import os
import json

def filter_and_save(articles, filename="sent_articles.txt"):
    if not os.path.exists(filename):
        with open(filename, "w") as f: f.write("")
    
    with open(filename, "r") as f:
        sent_links = set(f.read().splitlines())
    
    new_articles = [a for a in articles if a["link"] not in sent_links]
    
    return new_articles

def send_to_discord(webhook_url, articles):
    if not articles:
        print("No new articles to send.")
        return

    # Discord 限制一次 Embed 數量，我們分批發送或合併發送
    # 這裡採用合併發送，若文章太多則分段
    for i in range(0, len(articles), 10):
        batch = articles[i:i+10]
        embeds = []
        for a in batch:
            embeds.append({
                "title": a["title"],
                "url": a["link"],
                "color": 3447003 # 藍色
            })
        
        payload = {
            "username": "PTT Movie Tracker",
            "embeds": embeds
        }
        
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            print(f"Successfully sent {len(batch)} articles to Discord.")
            # 發送成功後才紀錄
            with open("sent_articles.txt", "a") as f:
                for a in batch:
                    f.write(a["link"] + "\n")
        else:
            print(f"Failed to send to Discord: {response.status_code}, {response.text}")

# 修改後的 main 部分
if __name__ == "__main__":
    WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL not set.")
    else:
        articles = get_ptt_articles()
        new_articles = filter_and_save(articles)
        send_to_discord(WEBHOOK_URL, new_articles)
```

- [ ] **Step 2: 提交變更**

```bash
git add scraper.py
git commit -m "feat: add filtering and discord notification"
```

---

### Task 4: 設定 GitHub Actions 排程

**Files:**
- Create: `.github/workflows/daily_check.yml`

- [ ] **Step 1: 建立 GitHub Workflow 檔案**

```yaml
name: Daily PTT Movie Check

on:
  schedule:
    - cron: '0 2 * * *' # UTC 02:00 = 台灣 10:00
  workflow_dispatch: # 允許手動觸發測試

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Restore Cache
        id: cache-sent-articles
        uses: actions/cache@v4
        with:
          path: sent_articles.txt
          key: sent-articles-${{ github.run_id }}
          restore-keys: |
            sent-articles-

      - name: Run Scraper
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python scraper.py

      - name: Save Cache
        uses: actions/cache/save@v4
        if: always()
        with:
          path: sent_articles.txt
          key: sent-articles-${{ github.run_id }}
```

- [ ] **Step 2: 提交變更**

```bash
git add .github/workflows/daily_check.yml
git commit -m "ci: add github action for daily scheduling"
```

---

### Task 5: 驗證與說明

- [ ] **Step 1: 撰寫 `README.md` 指導使用者設定 Secrets**

```markdown
# PTT Movie Tracker

每天定時追蹤好雷/普雷文章。

## 如何設定
1. 在 GitHub 倉庫中前往 `Settings` -> `Secrets and variables` -> `Actions`。
2. 點擊 `New repository secret`。
3. Name: `DISCORD_WEBHOOK_URL`
4. Value: (貼上您的 Discord Webhook URL)
5. 前往 `Actions` 標籤，手動執行 `Daily PTT Movie Check` 來測試。
```

- [ ] **Step 2: 提交變更**

```bash
git add README.md
git commit -m "docs: add setup instructions to readme"
```
