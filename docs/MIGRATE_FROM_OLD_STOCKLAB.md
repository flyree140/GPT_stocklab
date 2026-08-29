# 從原本 StockLab 遷移

原本 Repository 使用 Vite/React；這次交付改為「靜態 HTML + JSON」，目的是讓每日分析、Pages 與免費模型更容易部署，並降低依賴與建置失敗機率。

## 建議保留

- 舊版建立備份分支。
- 舊版 README、研究紀錄或你想保留的 UI 截圖，可放到 `archive/old-vite-version/`，但不要保留舊 Pages workflow。
- 若舊版有你自行撰寫的股票名單，可轉成 `config/stocks.json`。

## 不建議混用

- 舊 `src/App.tsx` 與新版 `assets/app.js` 同時當入口。
- 舊 Vite Pages build 與新版 `pages.yml` 同時部署。
- 把 API 金鑰寫入前端 JavaScript。
- 回測時直接讀 `data/latest.json` 當成過去資料。

## 新版對照

| 舊版概念 | 新版位置 |
|---|---|
| React 畫面 | `index.html` + `assets/app.js` |
| GDELT 查詢 | `scripts/news_sources.py` |
| 技術指標 | `scripts/indicators.py` |
| ATR 風險 | `scripts/scoring.py` |
| 每日資料 | `data/latest.json` |
| 歷史回放 | `data/snapshots/` |
| 結果揭曉 | `data/results/` |
| 自動部署 | `.github/workflows/pages.yml` |
| 每日分析 | `.github/workflows/daily-update.yml` |
