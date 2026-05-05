# PTT Movie Tracker

每天定時追蹤 PTT Movie 版的「好雷」與「普雷」文章，並發送到 Discord 頻道。

## 功能
- 每天台灣時間 10:00 自動執行。
- 爬取最新一頁及往回推 5 頁（共 6 頁）。
- 自動過濾已發送過的文章，避免重複通知。
- 使用 GitHub Actions Cache 儲存已發送紀錄。

## 如何設定
1. **建立 Discord Webhook**：
   - 在您的 Discord 伺服器頻道設定中，選擇「整合」 -> 「Webhook」 -> 「建立 Webhook」。
   - 複製 Webhook URL。

2. **設定 GitHub Secrets**：
   - 在您的 GitHub 倉庫頁面，點擊 `Settings`。
   - 選擇左側選單的 `Secrets and variables` -> `Actions`。
   - 點擊 `New repository secret`。
   - Name 填入：`DISCORD_WEBHOOK_URL`
   - Value 填入：貼上您的 Discord Webhook URL。

3. **啟用 Actions**：
   - 前往 `Actions` 標籤分頁。
   - 如果 GitHub 顯示 Actions 已停用（新倉庫常有此提示），請點擊啟用。
   - 您可以點擊 `Daily PTT Movie Check` 工作流，然後點擊 `Run workflow` 手動測試執行。

## 本地測試
如果您想在本地執行測試：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="您的網址"
python3 scraper.py
```
