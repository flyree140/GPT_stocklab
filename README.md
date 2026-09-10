# StockLab 16 — Evidence First

免費 GitHub Pages + GitHub Actions 台股研究與模擬交易平台。

## v16 重點

- **新聞不只打分數**：顯示事件類型、可讀證據、影響路徑、確認條件、失效條件、下一個 KPI。
- **排除低價值內容**：靜態個股頁、一般促銷、會議花絮不再被當成強烈交易訊號。
- **Qwen 免費控制**：每天最多 6 則高價值事件交給 `Qwen/Qwen3-0.6B` 做證據分類；重複內容快取；正式分數由透明規則與決策閘門產生。
- **研究方向**：新聞、基本面、技術、法人籌碼、估值、大盤一起評估；缺資料就顯示缺值，不用 50 分冒充已評估。
- **現代圖表**：本地 SVG K 線、MA5/20/60、成交量、RSI/MACD/KD、支撐壓力與新聞日標記。
- **歷史快照**：`data/snapshots/YYYY-MM-DD.json` 保存每個成功執行日期。
- **試買模擬**：只有按下「揭曉」才讀取訊號日後價格。
- **Google Sheet 收藏**：附 Apps Script，支援跨裝置同步與 tombstone 刪除紀錄。
- **全市場名單**：官方免費來源更新上市/上櫃 universe；每日深度分析仍採限額以控制免費 runner。

## 直接覆蓋 GitHub

詳見 `docs/DEPLOY.md`。最重要的是：解壓後要把 `.github/`、`assets/`、`stocklab16/` 等直接放在 Repository 根目錄，不要再包一層資料夾。

## 第一次建議流程

1. Push 到 `main`。
2. Settings → Actions → General → Workflow permissions → `Read and write permissions`。
3. Settings → Pages → Source → `GitHub Actions`。
4. Actions → `Daily StockLab 16 research` → Run workflow。
5. 第一次可勾 `skip_qwen`，先確認新聞/價量/快照/Pages 都正常。
6. 第二次不勾 `skip_qwen`，測完整免費 Qwen 管線。

## 免費策略

GitHub runner 不應對全上市櫃每檔都跑生成模型。本版把工作拆成：

- 全市場：名單可搜尋。
- 深度池：`config/stocks.json` 內核心股票；可自行擴充。
- 新聞：Google News RSS 免費抓取。
- Qwen：每天上限 6 則，只做證據分類，不自由生成投資故事。
- 分數：透明規則計算，不把 LLM 語氣當成預測機率。

## 本機測試

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m stocklab16.quality
pytest -q
node tests/test_engine.mjs
python -m http.server 8000
```

## 重要限制

- 初始 `data/` 是**合成示範資料**，只用來預覽 UI 與回測流程；第一次 Daily Action 成功後會被真實抓取資料取代。
- 免費公開資料可能延遲、缺漏、改格式。
- 歷史回填不等於當年真的預先公開過的預測。
- 本工具不構成投資建議，也不保證任何報酬。

## 讓收藏進入每日深度分析

Google Apps Script 設好後，在 GitHub Actions Secrets 加 `FAVORITES_FEED_URL` 與 `FAVORITES_READ_TOKEN`。收藏股票會排在核心池之前，但每日深度總量仍受 `DEEP_STOCK_LIMIT` 限制，避免免費 runner 失控。
