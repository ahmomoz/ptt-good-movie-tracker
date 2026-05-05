# 設計文件：PTT 電影版「好雷/普雷」追蹤器

## 1. 目標
建立一個自動化工具，每天定時爬取 PTT Movie 版的文章，篩選出標題包含「好雷」或「普雷」的文章，並將其標題與連結發送到 Discord 頻道。

## 2. 核心功能
- **爬蟲邏輯**：
  - 抓取 `https://www.ptt.cc/bbs/movie/index.html`。
  - 包含最新一頁，並向後追蹤 5 頁（總共 6 頁）。
  - 處理 PTT 的 18 歲年齡確認（Cookie: `over18=1`）。
- **篩選條件**：
  - 標題必須包含「好雷」或「普雷」。
- **防重複機制**：
  - 使用 `sent_articles.txt` 紀錄已發送過的文章網址。
  - 結合 GitHub Actions Cache 跨日保存紀錄。
- **通知功能**：
  - 使用 Discord Webhook 發送 Embed 訊息。
- **排程執行**：
  - 使用 GitHub Actions，設定為每天台灣時間 10:00 執行。

## 3. 技術架構
- **語言**：Python 3.10+
- **套件**：`requests`, `beautifulsoup4`
- **環境**：GitHub Actions
- **儲存**：`sent_articles.txt` (由 Cache 管理)
- **密鑰管理**：GitHub Actions Secrets (`DISCORD_WEBHOOK_URL`)

## 4. 專案結構
- `scraper.py`: 核心爬蟲與發送邏輯。
- `requirements.txt`: Python 依賴套件。
- `.github/workflows/daily_check.yml`: GitHub Actions 排程設定。
- `sent_articles.txt`: 紀錄檔（執行中產生）。

## 5. 錯誤處理
- 若 PTT 網頁結構改變或連線失敗，需捕獲異常並記錄 log。
- 若 Discord Webhook 發送失敗，需記錄錯誤訊息。

## 6. 安全性
- Discord Webhook URL **絕對不可** 直接寫在程式碼中，必須透過環境變數傳遞。
