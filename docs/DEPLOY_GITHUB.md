# 部署到 GitHub Pages：完整操作

這個版本是純靜態網站，不需要 Node.js build。GitHub Pages 直接部署 Repository 根目錄，GitHub Actions 負責每天產生 JSON。

## 方案 A：建立新 Repository（最安全）

1. 在 GitHub 建立一個 **Public** Repository，例如 `stocklab-free-ai`。
2. 把 ZIP 解壓後，將資料夾內的所有檔案放到 Repository 根目錄。
3. 確認 `.github/workflows/` 也有被上傳；網頁介面有時會隱藏點號開頭資料夾。
4. 開啟 **Settings → Pages**。
5. 在 **Build and deployment** 將 Source 選成 **GitHub Actions**。
6. 開啟 **Settings → Actions → General → Workflow permissions**，允許工作流程寫入 Repository；`daily-update.yml` 需要提交新的 `data/*.json`。
7. 到 **Actions → Daily free news analysis → Run workflow**，先手動跑一次。
8. 到 **Actions → Deploy GitHub Pages** 查看部署結果。

網址通常是：

```text
https://你的帳號.github.io/Repository名稱/
```

## 方案 B：更新既有 `flyree140/stocklab`

先備份舊版：

```bash
git clone https://github.com/flyree140/stocklab.git
cd stocklab
git switch -c backup-before-free-ai-v14
git push -u origin backup-before-free-ai-v14
git switch main
```

把新版 ZIP 解壓到另一個資料夾，再將新版內容複製到 `stocklab` 根目錄。建議確認差異後再提交：

```bash
git status
git add -A
git commit -m "feat: StockLab Free AI v14"
git push origin main
```

因為舊版是 Vite/React，新版是無 build 的靜態網站，最乾淨的方式是：

- 舊版保留在 `backup-before-free-ai-v14` 分支。
- `main` 改為新版。
- 不同時保留兩套入口與兩套 Pages workflow，避免部署衝突。

## 每日執行時間

`.github/workflows/daily-update.yml` 使用 GitHub 的時區排程：

```yaml
- cron: "20 18 * * 1-5"
  timezone: "Asia/Taipei"
```

這代表台北時間工作日 18:20。可自行改成 20:30：

```yaml
- cron: "30 20 * * 1-5"
  timezone: "Asia/Taipei"
```

排程可能不是精準到分鐘；若公開 Repository 長時間沒有活動，GitHub 也可能停用 scheduled workflow。可定期查看 Actions，或由自己手動 Run workflow。

## Hugging Face 模型

工作流程預設：

```yaml
ENABLE_HF_SENTIMENT: "1"
ENABLE_QWEN: "1"
QWEN_DAILY_LIMIT: "8"
```

不需要付費 API。模型會下載到 Actions cache。

若遇到 Hugging Face 下載限速：

1. 在 Hugging Face 建立唯讀 token。
2. GitHub Repository → **Settings → Secrets and variables → Actions**。
3. 新增 Secret：`HF_TOKEN`。

這是選用項目。請勿把 token 寫進 `.env` 後提交。

## 第一次執行與失敗備援

- 模型無法下載：自動改用透明規則。
- Qwen 太慢：手動執行 workflow 時勾選 `skip_qwen`。
- 某檔股票抓取失敗：保留可用股票，並標記 stale；如果全部價格都不可用，腳本拒絕覆蓋原資料。
- Google Sheets 最愛與每日 Action 無耦合；Apps Script 失效不會阻止網站更新。

## 自訂股票清單

修改 `config/stocks.json`：

```json
{
  "symbol": "2330",
  "market": "TWSE",
  "name": "台積電",
  "industry": "半導體",
  "aliases": ["台積電", "TSMC"],
  "news_query": "台積電 OR TSMC"
}
```

- 上市：`market` 使用 `TWSE`。
- 上櫃：使用 `TPEX`；價格主來源會改為 Yahoo 的 `.TWO`。
- Query 不宜過度寬鬆，否則會抓到同名非公司新聞。

## 自訂每日置頂

修改 `config/settings.json`：

```json
{
  "daily_top_n": 5,
  "minimum_top_pick_composite": 55,
  "minimum_top_pick_completeness": 58,
  "maximum_top_pick_risk": 72,
  "minimum_top_pick_news_relevance": 0.55
}
```

置頂結果會寫到 `data/latest.json` 的 `top_picks`。

## 為什麼 Pages 會監聽 workflow_run

每日與歷史工作流程使用 `GITHUB_TOKEN` 提交 JSON。由工作流程產生的 push 不一定會再觸發另一個 push 型工作流程，因此 `pages.yml` 也監聽這兩個資料工作流程完成事件，並從 `main` 重新簽出最新提交後部署。這可避免資料已更新、網站卻仍停在舊版本。
