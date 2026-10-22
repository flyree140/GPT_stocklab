# StockLab v18：只放進 GitHub 的部署包

這不是簡報包，也不是展示包。解壓後，**裡面所有內容都可以合併覆蓋到原本的 GPT_stocklab 根目錄**，不用逐一挑檔案。
本包是現有網站的升級部署包，需要你原本的正式資料；不是空白 Repository 的首次安裝資料包。

## 你只要做四件事

1. 先備份目前 Repository。不要清空舊專案。
2. 解壓本 ZIP，把裡面的所有檔案及資料夾「合併」到 Repository 根目錄；同名程式檔選覆蓋。**一定要包含 `.github/`。** 不要多包一層 StockLab 資料夾；不要用整個空資料夾取代舊的 `data/` 或 `config/`。
3. Commit 並 Push 到 `main`。GitHub Pages 的 Source 保持 GitHub Actions。
4. Actions → **Update Life Mode** → **Run workflow**。它讀取你既有資料，重算衍生報告與規劃資料，不啟動 Qwen。成功後，**Deploy StockLab 16 Pages** 會接續部署（名稱沿用原版）。

若首頁提示缺少 `data/life/latest.json`，先完成第4步，不要拿以前下載的舊 JSON 填回去。
之後需要抓取新新聞與行情，再執行 **Daily StockLab 16 research**；這個工作流程與「重新整理部署包」不同。
若 Actions 沒有新增項目，先確認 `.github/workflows/` 確實位於 GitHub 根目錄。

## 本包每個資料夾的用途

| 檔案／資料夾 | 處理方式 | 用途 |
|---|---|---|
| `.github/` | 整個合併上傳 | 每日更新、重算、測試與部署；不可漏掉 |
| `assets/`、`*.html`、`runtime.json` | 上傳並覆蓋同名檔 | 網站、帳本介面、圖表與教學 |
| `stocklab16/`、`stocklab17/`、`stocklab18/` | 三個全部上傳 | 程式互有相依，不是可任選的三個版本 |
| `tests/`、`requirements*.txt` | 全部上傳 | Actions 要執行的檢查與套件清單 |
| `config/*.default.json` | 上傳 | 缺少個人設定時的預設檔；不蓋掉正式設定 |
| `data/demo/` | 上傳 | 標示為示範的測試固定資料；不是你的真實行情 |
| `google-apps-script/` | 可以一併上傳 | 收藏同步原始碼；上傳 GitHub 不等於更新 Google Apps Script 部署 |
| `docs/`、`README.md`、`START_HERE.md`、其他根目錄小檔 | 一起上傳即可 | 少量必要文件、啟動與檢查檔 |

## 這些既有檔案必須保留；本包不包含它們

- `.git/`（僅在本機 Repository 存在，不是要上傳的資料夾）
- `data/latest.json`、`data/manifest.json`、`data/universe.json`
- 正式 `data/snapshots/`、`data/market/`、`data/system/`
- `config/stocks.json`、`config/settings.json`、`config/market-calendar.json`
- 已存在的 `data/life/`、`data/evaluation/`、`data/plans/`、`data/plan_runs/`

重算工作流程只更新衍生資料，原始快照保留。**部署包不附舊的衍生 JSON**，避免覆蓋你後來產生的新結果。
設定檔要用「合併檔案」方式更新，不能整個刪除資料夾。

## 已從舊完整包移除，不必再上傳的內容

- `report18/`：PowerPoint、PDF、報告附件與重複的CSV。
- `previews18/`：截圖、相簿與渲染記錄。
- `qa/`：僅供本次開發使用的畫面渲染腳本。
- 舊建置報告、舊SHA清單及重複部署文件。
- 以前那次執行產生的 `data/life/`、`data/evaluation/`、`data/plans/`。

簡報和PDF留在電腦即可。本部署包移除了指向已移除PDF的按鈕；**逐日比對、成果頁、CSV下載仍由實際資料重算後提供**。
舊 Repository 中若已留有 report18/、previews18/ 或 qa/，可暫時不刪，不影響這次升級；新版 Pages 打包不會把簡報和預覽搬上網站。

## 個人帳本與設定

保持相同 GitHub Pages 網址及路徑、同一瀏覽器使用，不要清除網站資料。
此部署包未改動瀏覽器儲存鍵與投資／帳務計算程式。仍建議升級前按一次「下載私人備份」。
**私人帳本備份、成交CSV、券商帳密、Token都不能上傳公開Repository。**
Google Sheets 原功能只同步收藏；不會因為上傳這包而自動同步實際帳本。

## 驗證界線

本次是部署檔案整理與本地驗證，不是重新驗證策略收益，也沒有替你提交 GitHub 或執行券商交易。
真實 GitHub 工作流程、外部新聞連線、Qwen下載與Google授權仍以你的實際部署結果為準。
詳見 `BUILD_REPORT.md`。
