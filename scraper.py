import requests
from bs4 import BeautifulSoup
import time
import os

def get_ptt_articles(pages=6):
    base_url = "https://www.ptt.cc"
    url = f"{base_url}/bbs/movie/index.html"
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": "over18=1"}
    all_articles = []

    for _ in range(pages):
        try:
            print(f"Fetching {url}...")
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
            paging_buttons = soup.select(".btn-group-paging a")
            if len(paging_buttons) >= 2:
                prev_link = paging_buttons[1]
                if prev_link and "href" in prev_link.attrs:
                    url = base_url + prev_link["href"]
                else:
                    break
            else:
                break
            time.sleep(0.5) # 稍微延遲避免被封 IP
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            break
            
    return all_articles

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

if __name__ == "__main__":
    WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    if not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL not set.")
        # 為了本地測試，如果沒設環境變數就只抓取不發送
        articles = get_ptt_articles()
        new_articles = filter_and_save(articles)
        print(f"\nFound {len(new_articles)} new articles (out of {len(articles)} total).")
        for a in new_articles[:3]:
            print(f"- {a['title']} ({a['link']})")
    else:
        articles = get_ptt_articles()
        new_articles = filter_and_save(articles)
        send_to_discord(WEBHOOK_URL, new_articles)
