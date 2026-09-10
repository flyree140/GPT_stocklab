# Google Sheets 我的最愛同步

1. 建立 Google Sheet → 擴充功能 → Apps Script。
2. 貼上 `Code.gs`。
3. Apps Script 專案設定 → Script properties 建立：
   - `STOCKLAB_TOKEN`：至少 20 字元，瀏覽器同步用。
   - `STOCKLAB_READ_TOKEN`：至少 20 字元，未來 GitHub 只讀 feed 可用，請與上面不同。
   - `ALLOWED_ORIGIN`：你的 Pages origin，例如 `https://flyree140.github.io`。
   - 若不是綁定式 Script，再加 `SPREADSHEET_ID`。
4. 部署 → 新增部署 → 網頁應用程式；執行身分選「我」、可存取選「任何人」。
5. 在 StockLab「方法設定」填 Web App URL、同步 Token、識別名稱並儲存。
6. 到「我的最愛」按「同步 Google Sheet」。

只存股票代號、名稱與個人備註。不要存券商帳密、API 私鑰、身分證或資產機密。

## 讓 GitHub 每日深度分析優先納入收藏

Repository → Settings → Secrets and variables → Actions，新增：

- `FAVORITES_FEED_URL`：Apps Script Web App URL
- `FAVORITES_READ_TOKEN`：Script properties 裡的 `STOCKLAB_READ_TOKEN`

Daily workflow 只讀 active symbols，最多取 30 檔，並仍受 `DEEP_STOCK_LIMIT` 控制。
