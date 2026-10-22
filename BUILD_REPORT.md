# StockLab v18 GitHub 部署專用包 — 本次整理驗證

## 目的與修改範圍

只把既有 v18 整理成可直接合併覆蓋的部署包，沒有重新改變投資策略、股數公式或實際帳務演算法。

- 移除 PowerPoint、PDF、預覽相簿、開發用畫面渲染腳本、重複文件與舊的衍生資料。
- 保留網站、教學、分析程式、GitHub workflows、工作流程使用的測試、預設設定及示範測試資料。
- 移除指向包內已移除 PDF 的三個下載按鈕；成果和教學頁改連線上逐日比對，CSV仍保留。
- Pages不再複製 report18，避免既有Repository殘留的簡報被一起發布。
- Update Life Mode同時更新舊版 planner頁的衍生資料，不會刪除原始快照。
- 分析核心、股數與記帳引擎、瀏覽器帳本儲存鍵均未修改。

## 本次實際通過

| 項目 | 結果 |
|---|---|
| 部署包Python回歸測試 | 94項通過 |
| 合併使用者上傳專案後，指定tests目錄重跑 | 94項通過 |
| 試買引擎JavaScript | 14項通過 |
| 股數／成本JavaScript | 12項斷言通過 |
| 生活版與帳本JavaScript | 34項通過 |
| 全部自有JS／教學內嵌JS、JSON格式與快照校驗 | 通過 |
| 頁面測試 | 10個分頁、23項檢查通過；JS錯誤0；缺少資料檔0 |
| 原資料保護 | 在使用者上傳的GPT_stocklab-main.zip副本上合併，91份正式資料／設定SHA-256保持不變；另測3個保護哨兵檔 |
| 打包內容 | 根目錄直接包含.github；不含正式data/latest.json、manifest、snapshots、market、system或自訂config |

## 驗證限制

瀏覽器環境禁止導航至localhost，因此頁面檢查使用實際HTML/CSS/ES模組、Python按需讀檔fetch與暫存localStorage適配器。資料使用舊v18包的衍生資料作離線測試；這些舊資料未放入新部署包。
沒有替使用者登入、推送GitHub或執行線上Actions，亦未重新驗證外部新聞端點、模型下載、Google授權或任何收益。
一次未指定tests目錄的完整合併目錄測試被時間限制中止；其後明確使用pytest -q tests重跑94項通過。
最終ZIP會另做乾淨解壓與重測，結果及檔案雜湊見相鄰的StockLab-v18-GITHUB-ONLY-VERIFICATION.json。
