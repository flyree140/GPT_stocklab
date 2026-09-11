# 本地推論限制與費用界線

- 模型：Qwen/Qwen3-0.6B，revision `c1899de289a04d12100db370d81485cdf75e47ca`；CPU，不要求付費推論API。
- 新模型嘗試：每日硬上限6次，失敗也算，狀態保存在data/system。
- 單次max_new_tokens=256、生成max_time=90秒、包含模型載入的子程序最多120秒；整批上限720秒。
- 一次子程序失敗／逾時後，本批改用規則，不不停重試。
- 明確數字／EPS事件多用規則，不耗Qwen；重複內容回快取。
- 快取最多1000個事件分類項目；模型權重cache在.cache/huggingface，Pages不公開。
- 20檔深度分析預設；全市場名單可搜尋但不代表全市場都有完整新聞／指標。
- 21:17台北備援若今日已成功更新則跳過。

這是程式內限制，不是對所有帳戶零費用的保證。公開repo標準runner、私人repo用量、儲存及額外runner設定請以GitHub官方規則為準。未實際驗證此使用者的帳單或授權環境。

Qwen模型卡：https://huggingface.co/Qwen/Qwen3-0.6B
GitHub Actions計費：https://docs.github.com/en/billing/concepts/product-billing/github-actions
