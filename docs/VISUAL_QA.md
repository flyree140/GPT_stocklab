# 視覺與互動驗收範圍

預覽截圖使用發布版本的真實HTML、CSS、JavaScript及按需載入的JSON，不是美工概念圖或AI生成圖。

## 環境限制與替代方式

本環境Chromium禁止一般網址導覽。因此驗收以about:blank載入原始DOM/CSS，將發布模組放到blob URL，fetch以測試用按需讀檔適配器提供原JSON。localStorage改用相同接口的記憶體Storage、history.replaceState為no-op。這些僅存在qa/測試工具，不會注入正式資產。

所以測到的是前端計算、互動、DOM及版面；不是GitHub線上部署、真實新聞請求、Qwen權重、Sheets跨網域授權或瀏覽器重開後持續儲存。這些未測項目在report列明。

發布相對URL、HTTP資產、Pages staging、manifest path另以本機HTTP實測，包含 `/GPT_stocklab/` 子路徑。

## 畫面與行為

桌機1440px；手機390/360/320px。主要頁面與展開新聞、個股dialog、教學頁都檢查document.scrollWidth，不讓手機layout viewport被內容撐大。圖表與行情表允許內部水平滑動。

新聞搜尋、EPS子類別、逐字證據、公司別KPI、圖表三指標、日期範圍／游標、收藏與刪除、歷史日期、試買取消／確認、教學計算器與測驗均有斷言。

發現並修復：

- 手機導覽min-content造成整頁寬於裝置，已限制grid minmax及局部水平捲動。
- 搜尋Enter開啟dialog後又觸發close按鈕，已阻止預設按鍵動作。
- 小螢幕K線初始水平位置，已預設顯示最新端；可左右滑。
- v16.1相依taxonomy缺檔、教學導覽和Pages遺漏，已補齊。

預覽採清楚標記的合成行情／財務資料與使用者標題案例；不能當成即時行情、已核實新聞或投資績效。

## 重跑

```bash
pip install playwright
# 系統需自行安裝Chromium；下面工具使用/usr/bin/chromium
python qa/browser_acceptance.py --output ../previews
```

機器可驗證結果：qa/BROWSER_REPORT.json；全套建置結果：BUILD_REPORT.json。
