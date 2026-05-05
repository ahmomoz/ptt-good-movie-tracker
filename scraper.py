import requests
from bs4 import BeautifulSoup
import time
import os
import re

def get_ptt_articles(pages=6):
    base_url = "https://www.ptt.cc"
    url = f"{base_url}/bbs/movie/index.html"
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": "over18=1"}
    all_articles = []

    for _ in range(pages):
        try:
            print(f"Fetching list {url}...")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 抓取文章列表
            for entry in soup.select(".r-ent"):
                title_tag = entry.select_one(".title a")
                date_tag = entry.select_one(".date")
                if title_tag and date_tag:
                    title = title_tag.text
                    link = base_url + title_tag["href"]
                    date = date_tag.text.strip()
                    # 篩選標題
                    if "好雷" in title or "普雷" in title:
                        all_articles.append({
                            "title": title, 
                            "link": link, 
                            "date": date
                        })
            
            # 尋找上一頁連結
            paging_buttons = soup.select(".btn-group-paging a")
            if len(paging_buttons) >= 2:
                prev_link = paging_buttons[1]
                if prev_link and "href" in prev_link.attrs:
                    url = base_url + prev_link["href"]
                else:
                    break
            else:
                break
            time.sleep(0.2)
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            break
            
    return all_articles

def get_article_preview(url):
    """進入文章頁面抓取前 100 字摘要"""
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": "over18=1"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 移除文章中的 meta 資訊與簽名檔
        main_content = soup.select_one("#main-content")
        if not main_content:
            return ""
            
        # 複製一份以免影響原對象，過濾掉 meta 與 push
        for tag in main_content.select(".article-metaline, .article-metaline-right, .push"):
            tag.decompose()
            
        text = main_content.get_text()
        # 移除空白與特殊字元
        text = re.sub(r'\s+', ' ', text).strip()
        # 截取前 100 字
        return text[:100] + "..." if len(text) > 100 else text
    except Exception as e:
        print(f"Error fetching preview for {url}: {e}")
        return "無法讀取預覽內容"

def filter_and_save(articles, filename="sent_articles.txt"):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("")
    
    with open(filename, "r") as f:
        sent_links = set(f.read().splitlines())
    
    new_articles = [a for a in articles if a["link"] not in sent_links]
    
    return new_articles

def send_to_discord(webhook_url, articles):
    if not articles:
        print("No new articles to send.")
        return

    # Discord 限制一次 Embed 數量為 10，我們分批發送
    for i in range(0, len(articles), 10):
        batch = articles[i:i+10]
        embeds = []
        for a in batch:
            print(f"Fetching preview for: {a['title']}")
            preview = get_article_preview(a["link"])
            
            embeds.append({
                "title": a["title"],
                "url": a["link"],
                "description": f"**日期**: {a['date']}\n\n{preview}",
                "color": 3447003 # 藍色
            })
            time.sleep(0.5) # 抓取文章內容之間稍微間隔
        
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

if __name__ == "__main__":
    WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL not set.")
        articles = get_ptt_articles(pages=3) # 測試抓 3 頁
        new_articles = filter_and_save(articles)
        print(f"\nFound {len(new_articles)} new articles.")
        for a in new_articles[:2]:
            preview = get_article_preview(a["link"])
            print(f"\n- 標題: {a['title']}")
            print(f"  日期: {a['date']}")
            print(f"  摘要: {preview}")
    else:
        articles = get_ptt_articles()
        new_articles = filter_and_save(articles)
        send_to_discord(WEBHOOK_URL, new_articles)
