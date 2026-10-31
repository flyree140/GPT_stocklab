# 免費設計與實際上限（19.3）

這裡不是Qwen商用API配額。模型權重在CPU本地推論；你使用的是GitHub runner運算、儲存與外部資料來源。

- 預設：每個workflow run最多6次新嘗試；台北每日共12次。GITHUB_RUN_ID識別同輪重試。
- 可調硬上限：每日24次、每輪12次。環境變數 QWEN_DAILY_LIMIT、QWEN_RUN_LIMIT。無限制值會被截到硬上限。
- 模型程序整批720秒，超時停止。不是保證每則有結果。
- 每批模型只載入一次；每則成功結果即時保存，後面超時不丟前面結果。
- 原版／自有adapter共用 data/system/qwen-state.json；啟用自有adapter時停用舊生成。
- 失敗仍算新嘗試。成功快取不再次計數，None不是成功快取。相同workflow不反覆嘗試同一失敗事件。
- 每檔最多20則RSS（上限40），整體預設20檔。來源範圍有限，並非全網、全語言或全篇全文。
- 日期／提示／模型或adapter版本改變會影響快取鍵，不能用舊答案冒充新模型輸出。
- GitHub公開repo標準runner運算免費；artifact/快取/付費runner/私人repo須依帳號核對。
- 不自動購買Colab GPU、不保活、不繞過社群授權或速率限制。

官方說明：
https://docs.github.com/en/billing/concepts/product-billing/github-actions
https://research.google.com/colaboratory/faq.html
