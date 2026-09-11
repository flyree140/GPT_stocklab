# StockLab 16.1.2 建置／視覺驗收報告

## 已完成

| 檢查 | 結果 |
|---|---|
| Python語法、前端模組／教學JS語法 | 通過 |
| 自有JSON與日期／快照雜湊 | 通過（來源18份JSON） |
| Python回歸 | **58項通過** |
| JavaScript試買引擎 | **14項通過** |
| 瀏覽器行為斷言 | **32項通過** |
| 桌機／手機版面檢查 | **33組通過**；手機390/360/320px |
| Chromium執行錯誤 | **0** |
| 實際程式預覽截圖 | **16張**（另有便於預覽的裁切圖） |
| Pages /GPT_stocklab/ HTTP資產／JSON路徑 | **44次成功** |
| Pages私有模型狀態請求 | **404，未公開** |
| 原v16包覆蓋前後保護檔 | **15份位元組保持一致** |
| v16離線重算 | 原快照、市場歷史、自訂設定不變；新run另存 |

原v16測試樣本來自先前交付的StockLab-v16-COMPLETE.zip，不是聲稱已取得或驗證使用者目前的GitHub線上資料。

## 視覺驗收方式

使用發布版HTML/CSS/JavaScript與按需讀取JSON，在Chromium渲染並操作。由於執行環境禁止一般網址導覽，瀏覽器測試採file-backed fetch、blob模組、記憶體Storage及history no-op適配器（僅測試工具使用）。原生HTTP相對路徑另行驗證。

實際檢查並修復手機導覽撐寬、Enter搜尋關閉dialog和手機K線最新端顯示問題。圖片為合成行情／財務與明示教學案例，不是可交易訊號。

## 未宣稱完成

真實GitHub Actions runner、模型權重下載／Qwen推論、新聞供應商當日可用性、Google Sheets跨網域授權、瀏覽器關閉後localStorage持久性，本次未做線上端到端驗證。這些需部署後以自身帳號驗證。

## 檔案

- 完整命令輸出：BUILD_REPORT.json
- 視覺／互動／資料請求記錄：qa/BROWSER_REPORT.json
- 覆蓋、重算、HTTP測試：qa/PACKAGE_ACCEPTANCE.json
- 檔案校驗：FILE_MANIFEST.sha256
- 最終ZIP乾淨解壓再測：與ZIP另外提供的VERIFICATION.json

本包不覆蓋正式data或自訂config，避免預覽資料蓋掉原站。覆蓋後請執行Re-analyze saved snapshots，否則舊JSON裡的+19不會自動重算。
