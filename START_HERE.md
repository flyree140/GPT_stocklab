# StockLab 16.1.2 — 保留資料覆蓋版

先備份，再把 ZIP 內容直接合併到原 Repository 根目錄。**不要刪除舊 data/、config/ 或 .git/；不是整個專案先清空。**

## 這包刻意不放入的檔案

`data/latest.json`、`data/manifest.json`、正式 `data/snapshots/`、正式 `data/market/`、`config/stocks.json`、`config/settings.json`。
因此單純覆蓋本包不會蓋掉既有正式資料、歷史快照或自訂股票池。新增的預覽資料只在 `data/demo/`；預設設定只在 `config/*.default.json`。

## 更新既有 v16：請先做這一步

程式更新不會魔法般改寫已儲存的 +19 舊結果。

1. Commit / Push 到 `main`，包含隱藏的 `.github/workflows/`。
2. Actions → **Re-analyze saved snapshots** → Run workflow。
3. 此工作流程不呼叫 Qwen；用新證據規則重算相容 v16 快照，原快照原位保留，新結果另存 run 檔，標示「事後重算」。
4. 完成後 **Deploy StockLab 16 Pages** 會接續部署；也可手動執行。
5. 開網站確認頁尾 **StockLab 16.1.2**，日期與資料狀態正確，再點 **教學實驗室**。

若 `migration-report.json` 記錄 `preserved_unconverted`，代表舊資料格式不相容，系統保留原檔而不猜測轉換；再執行 Daily 建立新的相容快照。

## 初次安裝或取得今日新資料

Actions → **Daily StockLab 16 research** → Run workflow；`as_of` 留空，第一次保留 `skip_qwen` 勾選（預設）。先確認行情／新聞／新規則與部署；下一次再取消勾選測試本地 Qwen。

既有設定仍是 Settings → Pages → Source: GitHub Actions；Actions 要有內容寫入權限才能提交資料。這些設定不會透過 ZIP 自動替你修改。

教學頁：`tutorial.html`，可獨立用瀏覽器打開。
網站預覽：在專案目錄執行 `python -m http.server 8000`，再開 `http://localhost:8000/?demo=1`。
網站本體需要 HTTP，不支援直接雙擊 `index.html` 讀取 JSON。

更多操作：`docs/DEPLOY.md`；測試範圍：`BUILD_REPORT.md`；圖形驗收方法：`docs/VISUAL_QA.md`。
