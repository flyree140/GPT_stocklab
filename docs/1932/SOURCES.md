# 19.3.2來源與取用邊界（查詢日2026-10-31）

1. 參考網站 https://kmuftp-creater.github.io/tw-stock-analyzer/ — 借鑑快速健檢、條件篩選、持有者/進場者分工；沒有複製程式或假定其固定停利/停損有效。
2. TWSE月營收 https://data.gov.tw/dataset/18420 ; https://openapi.twse.com.tw/v1/opendata/t187ap05_L — 官方資料集標示政府開放資料授權1.0與免費；核對出表日、資料年月、金額單位。取得時間不是歷史發布時間。
3. TWSE法人 T86 https://www.twse.com.tw/rwd/zh/fund/T86?response=json — 外資/投信/自營商買賣超股數，沒有外資真實持倉成本。程式按欄名、回應日期解析。
4. TPEx法人 https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading — 上櫃來源與TWSE分開；本環境查詢403，尚未實際驗證最新回應。程式欄位或日期不符即顯示缺值，不套TWSE代替。
5. TPEx英文欄名參考 https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/data_provider/tw_institutional_fetcher.py — 原始作者的資料接頭文件；本版僅參考API欄位定義，未複製其實作。仍需執行環境核對官方回應。
6. Financial PhraseBank https://huggingface.co/datasets/takala/financial_phrasebank — CC BY-NC-SA 3.0，4,846句英文金融情緒、AllAgree2,264；provider版本可能變，實際下載數以檔案為準。沒有逐則時間、不是台股未來報酬標準答案；預設不下載，需同意授權。舊dataset script已不受新datasets viewer支援，本版固定repo SHA讀原ZIP。
7. FinQA https://github.com/czyssrs/FinQA ; LICENSE MIT — 財務數字推理；保留train/dev/test。Repository授權不自動解除第三方財報文件權利。下載原檔，不假裝已轉成StockLab因果教材。
8. SEC https://www.sec.gov/search-filings/edgar-application-programming-interfaces — submissions索引無API key；本collector只取索引，不宣稱原文皆已下載。使用自己的聯絡User-Agent，遵守fair access，不繞過限流。
9. GitHub計費 https://docs.github.com/en/billing/concepts/product-billing/github-actions — 公開Repository標準runner運算免費；儲存及其他方案另計，程式沒有存取使用者帳單。
10. Colab FAQ https://research.google.com/colaboratory/faq.html — 免費GPU/型號/時間不保證，不能多帳號規避、常駐服務或保活。
11. Qwen3-0.6B https://huggingface.co/Qwen/Qwen3-0.6B — 原模型；LoRA仍需固定基底。本版沒有新增付費模型API。
12. PEFT LoRA https://huggingface.co/docs/peft/en/developer_guides/lora — 基底+adapter；不能只拿adapter當完整語言模型。
13. FinGPT https://github.com/AI4Finance-Foundation/FinGPT — 金融指令任務參考，不等於可無限免費使用的新聞API；逐資料集核對授權。
14. Qlib https://github.com/microsoft/qlib — 量化研究/資料處理參考，不提供全市場即時免費數據保證。

本執行環境外部DNS無法連線，HF/TWSE/GitHub下載均未成功，因此新外部資料是在使用者Colab執行時取得。隨訓練包提供的600筆**真實待核對標題**來自使用者上傳的GPT_stocklab-main.zip；沒有將舊分數當gold，沒有將公開可讀當成訓練權利已確認。請保持私人。
