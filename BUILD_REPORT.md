# StockLab PaperLab 19.2｜建置與驗證報告

## 實際通過

- Python：134項（含新增33項）。
- JavaScript：140項既有試驗、帳務、成本、雲端格式與日期檢查。
- Notebook：24格／14格程式，nbformat與語法合格；預設CPU路徑完整執行，0錯誤。TRAIN_NOW=False。
- 瀏覽器：9項研究頁／教學／導覽與320、360、390px版面檢查，0 JavaScript錯誤。
- 與使用者提供的GPT_stocklab-main.zip合併：91份正式資料與設定SHA-256保持不變。
- 真實上傳檔案的20檔股票可產生CPU研究附檔，沒有模型呼叫，不改原快照。
- 工作流程YAML已解析；ZIP另做解壓及雜湊驗證。

## 範圍限制

本環境無CUDA訓練，容器無法透過DNS取得模型。沒有執行真GPU微調、Qwen/adapter下載、使用者帳號授權或GitHub實際排程。沒有讀取使用者Billing或剩餘額度，沒有模型精度或投資報酬改善的證明。

瀏覽器的HTTP導航遭環境政策阻擋，因此使用實際發布HTML/CSS/JS搭配離線fetch適配器渲染，資料為合成示例；不宣稱正式網站或真實Google/HF API已測通。

## 發布與資料保護

部署包的data只含data/demo，config只含default/example；不帶正式latest、manifest、快照、市場歷史、cloud-config.json或自訂設定。依路徑合併，不先刪掉data/config；stocklab16/17/18是既有相依模組，stocklab192是新增。

自己的adapter預設關閉、僅影子輸出，與舊Qwen共用每日6次嘗試。LoRA訓練與比較成功、資料授權核對後，才能明確設定GitHub Variables/Secret。合成練習權重禁止進入網站研究流程。
