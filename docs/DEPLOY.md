# v16.1.2 保留資料覆蓋與部署

## 1. 備份

先在 GitHub 建立 `backup-before-16-1-2` 分支，或下載目前 Repository ZIP。瀏覽器收藏儲存在原站網址的 localStorage，另可用Google Sheets同步備份。網站路徑／網域改變時，瀏覽器本機儲存不會自動搬家。

## 2. 合併覆蓋，不能清空原專案

建議用 GitHub Desktop 打開 `flyree140/GPT_stocklab` 本機目錄。把發布 ZIP 裡面的內容直接合併進根目錄，覆蓋程式同名檔。

- **保留 `.git/`、`data/`、`config/`。** 不執行「刪除全部舊檔」。
- ZIP 的 `.github/` 是隱藏資料夾，也要複製。
- `index.html` 應直接出現在 Repository 根目錄，不能再套一層資料夾。
- 確認 `git diff` 中正式data快照、custom config沒有因複製而被刪除。
- Commit並Push main；不會替你自動授權帳號、寫入GitHub或修改設定。

本包不含 `config/stocks.json`、`config/settings.json`，預設值另存在 `*.default.json`。已存在的自訂設定優先，沒有才使用預設。

## 3. 重要：先重算已保存的新聞

**只更新程式，舊latest裡的固定+19仍可能不變。**

Actions → **Re-analyze saved snapshots** → Run workflow。

工作流程只讀原保存的新聞與當時價量，用新規則產生新run，原快照保留。結果有「事後重算」標示，模型不耗新推論次數。`data/system/migration-report.json`記錄哪些完成、哪些保留未轉換。

若沒有此工作流程，檢查`.github/workflows/migrate.yml`是否在main的正確根目錄。

## 4. 部署

既有設定保持：

- Settings → Pages → Build and deployment → Source：GitHub Actions。
- Actions具有寫入contents權限，才可commit新資料。

重算成功會接續 **Deploy StockLab 16 Pages**；也可手動Run。此流程將教學頁、assets、資料部署到Pages，排除data/system。

公開入口仍是 `https://flyree140.github.io/GPT_stocklab/`。

若你曾自行加過不同檔名的舊Daily／歷史workflow，ZIP不會幫你刪除；先停用重複的v14/v15排程，避免舊程式覆蓋新結果或重複消耗runner。

## 5. 今日資料與Qwen

Actions → **Daily StockLab 16 research** → Run workflow。

`as_of`留空；先勾選`skip_qwen`確認行情、RSS、新規則和部署能通。之後再取消勾選啟用小模型。預設深度20檔、每日6次Qwen新嘗試，失敗同樣計入。

你不必先買OpenAI/HuggingFace推論API。這是runner本地模型，實際runner、儲存與帳戶付費設定由GitHub帳戶管理；本包不開通額外付費資源。

## 6. 檢查網站

頁尾應為 **StockLab 16.1.2**。新聞卡有數字擷取、分類、分數公式及公司別追蹤點。頁面顯示示範模式時，不能用示範價量交易；有正式資料的Pages由stage自動切成production，`?demo=1`可主動看展示資料。

教學頁 `tutorial.html` 可獨立雙擊；網站 `index.html` 需要HTTP服務讀取JSON。

## 7. 回復

以GitHub備份分支恢復程式；若僅需看舊研究結果，歷史頁仍保留原run。不要為了回復而刪除整個快照目錄。任何手動刪除請先另存備份。

## 官方參考（以官方當時規則為準）

- GitHub Pages自訂workflow：https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- 手動工作流程：https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- Actions計費：https://docs.github.com/en/billing/concepts/product-billing/github-actions
