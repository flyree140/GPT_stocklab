# StockLab 19.3.3｜更新、批次日結與Google教學修補

## 只合併，不清空

這是可直接合併到19.3.2的GitHub專用完整部署包。解壓內容全部合併到Repository根目錄，包含`.github/`。不要刪除舊data、config或瀏覽器localStorage。

不攜帶正式data/latest.json、data/manifest.json、data/market、正式snapshots、config/stocks.json、config/settings.json或cloud-config.json。原正式資料與自訂設定保留。data/demo僅是明確合成測試。

**Colab Notebook／LoRA權重不修改，不需要重訓。**

## 提交後首次使用

1. 到Actions，執行 **Refresh market data (no Qwen)** → Run workflow。
2. 確認它成功，再確認 **Deploy StockLab 16 Pages** 綠色完成（名稱沿用）。
3. 回網站強制重新整理Ctrl+Shift+R，不清除網站資料。
4. 進「開發者驗證台」。看台北時間、研究日期、行情補價工作狀態。
5. 開「已確認批次」，按 **更新已發布行情並結算**。
6. 查看本次買進、賣出、確定未成交與仍待處理數量，以及每列有效日與缺少資料。
7. 開「Google活頁簿」，沿用公開Client ID，登入→尋找／建立→保存並讀回核對。詳developer-help.html。

## 新排程（台北時間）

- 08:17、21:17：既有每日新聞研究。Qwen預設每批6次，一天12次共用。
- 週一至五09:17、12:17：CPU行情檢查，只補前一完整交易日。
- 週一至五14:17、16:17、21:47：CPU盤後補價／重試與被動結果更新。

GitHub不保證排程準時，來源未公布就保留缺失。新流程不安裝或呼叫模型。所有寫資料的工作共用同一concurrency group，避免同時git push衝突。

## 不是即時撮合

本版本仍採訊號後下一有效日開盤的日K代理成交。你在今天開盤後才確認的最新提案，不會倒填今天9點買進；有效日通常為下一交易日。確認也不會立即成交。只有有效日結束、完整日K已發布，才回算。

頁面按鈕會重新下載發布資料（cache bust、no-store），不會把私人批次送給GitHub。公開Pages不能匿名啟動爬蟲；需即時要求補抓，透過你登入的Actions頁按Run workflow。不把GitHub token放前端。

## 個人資料

19.3.2既有批次版本、主鍵、原計畫雜湊保持相容。未通過只保留觀察；零試單不會被自動改成買進。Google開發者活頁簿與個人試驗帳本分開。登入與建表不是已同步，讀回核對後才顯示成功。
