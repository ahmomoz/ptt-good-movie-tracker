import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.ptt.cc"
SENT_ARTICLES_FILE = "sent_articles.txt"
MAX_ATTEMPTS = 3

PTT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def create_ptt_session():
    """建立共用的 PTT 連線，保留標頭與 Cookie。"""
    session = requests.Session()
    session.headers.update(PTT_HEADERS)
    session.cookies.set(
        "over18",
        "1",
        domain="www.ptt.cc",
        path="/",
    )
    return session


def parse_articles_from_soup(soup, base_url):
    """解析並篩選好雷、普雷、負雷文章。"""
    articles = []

    for entry in soup.select(".r-ent"):
        title_tag = entry.select_one(".title a")
        date_tag = entry.select_one(".date")

        if not (title_tag and date_tag):
            continue

        href = title_tag.get("href")
        if not href:
            continue

        title = title_tag.get_text(strip=True)

        if any(keyword in title for keyword in ("好雷", "普雷", "負雷")):
            articles.append({
                "title": title,
                "link": urljoin(base_url, href),
                "date": date_tag.get_text(strip=True),
            })

    return articles


def get_prev_page_url(soup, base_url):
    """取得上一頁 URL。"""
    for button in soup.select(".btn-group-paging a"):
        if "上頁" in button.get_text():
            href = button.get("href")
            return urljoin(base_url, href) if href else None

    return None


def fetch_ptt_list(session, url):
    """讀取列表，對連線問題、429、5xx 進行有限次重試。"""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(
            f"Fetching list {url} "
            f"(Attempt {attempt}/{MAX_ATTEMPTS})...",
            flush=True,
        )

        try:
            response = session.get(url, timeout=20)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            print("  - PTT connection failed or timed out.", flush=True)

            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    f"PTT 連線失敗，已嘗試 {MAX_ATTEMPTS} 次。"
                ) from None

            wait_time = attempt * 5
            print(f"  - Waiting {wait_time}s before retrying...", flush=True)
            time.sleep(wait_time)
            continue

        print(
            f"  - HTTP status: {response.status_code}; "
            f"Content-Type: {response.headers.get('Content-Type', '')}",
            flush=True,
        )

        if response.status_code == 403:
            snippet = re.sub(r"\s+", " ", response.text)[:500]
            print(f"  - Response preview: {snippet}", flush=True)

            raise RuntimeError(
                "PTT 回傳 HTTP 403，拒絕存取文章列表。"
                "本次抓取失敗，不能判定為沒有新文章。"
            )

        retryable = (
            response.status_code == 429
            or 500 <= response.status_code < 600
        )

        if retryable and attempt < MAX_ATTEMPTS:
            wait_time = attempt * 10
            print(
                f"  - Waiting {wait_time}s before retrying...",
                flush=True,
            )
            time.sleep(wait_time)
            continue

        if not response.ok:
            raise RuntimeError(
                f"PTT 列表讀取失敗，HTTP {response.status_code}。"
            )

        soup = BeautifulSoup(response.text, "html.parser")

        if soup.select_one(".r-list-container") is None:
            raise RuntimeError(
                "PTT 回應不是預期的文章列表，"
                "可能是驗證頁或其他回應，停止本次執行。"
            )

        return soup

    raise RuntimeError("PTT 列表讀取失敗。")


def get_ptt_articles(session, pages=6):
    """抓取指定頁數，任何列表抓取失敗都停止執行。"""
    url = f"{BASE_URL}/bbs/movie/index.html"
    all_articles = []
    seen_links = set()

    for page in range(pages):
        if not url:
            break

        print(f"\nReading page {page + 1}/{pages}", flush=True)
        soup = fetch_ptt_list(session, url)

        found = parse_articles_from_soup(soup, BASE_URL)
        print(
            f"  - Found {len(found)} candidate articles on this page.",
            flush=True,
        )

        # 避免置底或跨頁重複文章重複發送
        for article in found:
            if article["link"] not in seen_links:
                seen_links.add(article["link"])
                all_articles.append(article)

        url = get_prev_page_url(soup, BASE_URL)

        if url and page < pages - 1:
            time.sleep(1)

    return all_articles


def get_article_preview(session, url):
    """取得文章前 100 字；摘要失敗時仍允許發送文章連結。"""
    try:
        response = session.get(url, timeout=10)

        if not response.ok:
            print(
                f"  - Preview unavailable: HTTP {response.status_code}",
                flush=True,
            )
            return "無法讀取預覽內容，請點擊標題查看原文。"

        soup = BeautifulSoup(response.text, "html.parser")
        main_content = soup.select_one("#main-content")

        if main_content is None:
            return "無法讀取預覽內容，請點擊標題查看原文。"

        for tag in main_content.select(
            ".article-metaline, .article-metaline-right, .push"
        ):
            tag.decompose()

        text = main_content.get_text()

        # 移除常見的 PTT 簽名檔與文章尾端資訊
        text = re.split(r"\n--\s*\n", text, maxsplit=1)[0]
        text = text.split("※ 發信站:", 1)[0]
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return "此文章沒有可顯示的預覽內容。"

        return text[:100] + "..." if len(text) > 100 else text

    except requests.exceptions.RequestException:
        print("  - Preview request failed or timed out.", flush=True)
        return "無法讀取預覽內容，請點擊標題查看原文。"


def filter_new_articles(articles, filename=SENT_ARTICLES_FILE):
    """排除已成功發送的文章。"""
    if not os.path.exists(filename):
        return articles

    with open(filename, "r", encoding="utf-8") as file:
        sent_links = set(file.read().splitlines())

    return [
        article
        for article in articles
        if article["link"] not in sent_links
    ]


def send_to_discord(
    webhook_url,
    articles,
    session,
    filename=SENT_ARTICLES_FILE,
):
    """分批發送；確認成功後才寫入紀錄。"""
    if not articles:
        print("No new articles to send.", flush=True)
        return

    for start in range(0, len(articles), 10):
        batch = articles[start:start + 10]
        embeds = []

        for article in batch:
            print(
                f"Fetching preview for: {article['title']}",
                flush=True,
            )

            preview = get_article_preview(session, article["link"])

            embeds.append({
                "title": article["title"][:256],
                "url": article["link"],
                "description": (
                    f"**日期**: {article['date']}\n\n{preview}"
                ),
                "color": 3447003,
            })

            time.sleep(0.5)

        payload = {
            "embeds": embeds,
            "allowed_mentions": {"parse": []},
        }

        try:
            response = requests.post(
                webhook_url,
                params={"wait": "true"},
                json=payload,
                timeout=20,
            )
        except requests.exceptions.RequestException:
            # 不印出例外內容，避免洩漏含 Token 的 Webhook URL
            raise RuntimeError(
                "Discord 連線失敗或逾時，"
                "本批文章未寫入發送紀錄。"
                "若 Discord 已收到訊息但回應逾時，"
                "下次執行可能重複發送。"
            ) from None

        if response.status_code not in (200, 204):
            if response.status_code == 429:
                raise RuntimeError(
                    "Discord 回傳 HTTP 429，觸發發送頻率限制。"
                    "本批文章未寫入發送紀錄，請稍後再執行。"
                )

            raise RuntimeError(
                f"Discord 發送失敗，HTTP {response.status_code}。"
                "請檢查 Webhook 設定、頻道權限與訊息內容；"
                "本批文章未寫入發送紀錄。"
            )

        with open(filename, "a", encoding="utf-8") as file:
            for article in batch:
                file.write(article["link"] + "\n")

        print(
            f"Successfully sent {len(batch)} articles to Discord.",
            flush=True,
        )

        if start + 10 < len(articles):
            time.sleep(2)


def main():
    webhook_good = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    webhook_bad = os.getenv("DISCORD_WEBHOOK_URL_BAD", "").strip()

    # 在 Actions 中缺少所有 Webhook 時，直接報錯。
    # 本機未設定 Webhook 時，保留只抓取、不發送的測試模式。
    dry_run = not webhook_good and not webhook_bad

    if dry_run and os.getenv("GITHUB_ACTIONS") == "true":
        raise RuntimeError(
            "未設定 DISCORD_WEBHOOK_URL 或 DISCORD_WEBHOOK_URL_BAD。"
            "請檢查 GitHub Actions Secrets。"
        )

    if dry_run:
        print(
            "No Discord webhooks configured. Running local preview only.",
            flush=True,
        )

    with create_ptt_session() as session:
        articles = get_ptt_articles(
            session,
            pages=3 if dry_run else 6,
        )

        # 反轉列表，讓較舊的文章先發送
        articles.reverse()
        new_articles = filter_new_articles(articles)

        good_articles = [
            article
            for article in new_articles
            if "好雷" in article["title"] or "普雷" in article["title"]
        ]

        bad_articles = [
            article
            for article in new_articles
            if "負雷" in article["title"]
        ]

        print(
            f"\nFetched {len(articles)} unique candidate articles.",
            flush=True,
        )
        print(
            f"New good/normal: {len(good_articles)}; "
            f"new bad: {len(bad_articles)}",
            flush=True,
        )

        if dry_run:
            for label, group in (
                ("好雷／普雷", good_articles),
                ("負雷", bad_articles),
            ):
                print(f"\n{label}：{len(group)} 篇", flush=True)

                for article in group[:2]:
                    preview = get_article_preview(
                        session,
                        article["link"],
                    )
                    print(
                        f"\n標題：{article['title']}\n"
                        f"日期：{article['date']}\n"
                        f"連結：{article['link']}\n"
                        f"摘要：{preview}",
                        flush=True,
                    )
                    time.sleep(0.5)

            return

        # 一個分類發送失敗時，仍嘗試另一個分類
        failures = []

        for label, webhook, group in (
            ("good/normal", webhook_good, good_articles),
            ("bad", webhook_bad, bad_articles),
        ):
            if not webhook:
                print(
                    f"Webhook for {label} not configured; skipping.",
                    flush=True,
                )
                continue

            if not group:
                print(
                    f"No new {label} articles to send.",
                    flush=True,
                )
                continue

            print(
                f"Sending {len(group)} {label} articles to Discord...",
                flush=True,
            )

            try:
                send_to_discord(webhook, group, session)
            except RuntimeError as exc:
                failures.append(f"{label}: {exc}")
                print(f"ERROR: {label}: {exc}", flush=True)

        if failures:
            raise RuntimeError("；".join(failures))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 不直接輸出未知例外的內容，以免帶出機密網址
        message = (
            str(exc)
            if isinstance(exc, RuntimeError)
            else f"發生未預期錯誤，類型：{type(exc).__name__}"
        )
        print(f"ERROR: {message}", file=sys.stderr, flush=True)
        sys.exit(1)
