# StockLab 19.3.2｜GitHub專用合併包

只把本包解壓內容合併到Repository根目錄，包含 `.github`。不要清空舊專案，原正式 `data/`、`config/stocks.json`、`config/settings.json`、`cloud-config.json`、瀏覽器個人試驗均保留。

## 第一次操作

1. 備份目前Repository。合併本包並提交main（不是上傳ZIP檔本身）。
2. 執行 `Actions → Developer validation 19.3.2 → Run workflow`。`import_archive`預設開啟，舊快照登記為**回溯參考**，不是當年就保存的前瞻結果。`refresh_prices`預設最多40檔CPU補行情，不呼叫Qwen。
3. 確認 `Deploy StockLab 16 Pages` 成功；這個名稱為相容舊流程保留。
4. 網站導覽選 **開發者・全股票驗證** (`developer1932.html`)。每檔獨立虛擬本金，不占用個人4,000元帳。
5. 檢查全部配置與理由 → 一鍵確認全部合格試單 → 有完整日K後批次結算。未通過仍保留，被動追蹤全部股票1/5/10/20日。
6. 「全部分析驗證」要先按揭曉。沒有結果JSON時，先做第2步，不把資料故障當看空。

## 日常流程

原 `Daily StockLab 16 research` 保留08:17/21:17台北啟動設定（不保證準時完成）。預設20檔深度研究，以12核心＋8輪巡，最愛優先。每天原版與自有Qwen**共用12次新嘗試**、每批最多6次。抓新聞與CPU分析不占模型嘗試。

新增官方法人日表抓取、曾分析股票行情補充、全部訊號登記及成本後結果計算。未知日期、缺價格、公司行動不猜值。

`DEEP_STOCK_LIMIT` 可設1–30、`ROTATING_STOCKS` 預設8、`PRICE_REFRESH_LIMIT` 預設40（最高80），均是GitHub Actions Variables。更大不等於免費資源保證完成；保留平台限制與資料源節流。

## 你現在的合成adapter

保留作流程成功證據，**不要部署為正式研究，不改manifest繞過限制**。打開 `pipeline1932.html` 看全流程。

正式順序：D CPU真實來源/私人待核對清單 → annotation核對來源/時間/數字/訓練權利 → A MODE=reviewed → B GPU → E檢查與私人HF發布。

GitHub Variables：
- `STOCKLAB_192_ENABLED=1`（只有正式adapter準備好後）
- `STOCKLAB_ADAPTER_REPO=你的帳號/私人模型庫`
- `STOCKLAB_ADAPTER_REVISION=40位commit SHA`（不是main）

Secret：`HF_TOKEN` 只讀該庫。Daily取消skip_qwen；新結果先寫入影子研究，不改舊快照與既有試單。

## 個人／開發者／公開研究資料分離

- 原個人試驗保持既有storage key。
- 開發者批次在自己的新storage key，可下載備份。
- 開發者Google活頁簿獨立命名，不寫進個人帳本；沿用cloud-config Client ID。
- GitHub保存的是公開研究快照及被動研究結果，不會讀到你的瀏覽器私人持股。
- 新增雲端同步經測試替身驗證，尚未取得你的Google真實授權。

## 外資提醒不是外資真實成本

官方買賣超沒有完整成交成本及存量。這版只算「典型價×正淨買股數」的支撐代理，最低5期、近20期窗口完整、來源日期一致才顯示。資料缺漏、不新鮮、無淨買或跨公司行動時不畫線。每次取得保存首次可用時間，不把今天才下載的資料倒填成昨天就知道。

完整圖解與限制：`pipeline1932.html`。檢查紀錄：`BUILD_REPORT.md`。
