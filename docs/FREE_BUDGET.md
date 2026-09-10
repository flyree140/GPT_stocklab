# 免費運算預算

預設：

- Qwen3-0.6B 每日最多 6 個新事件。
- 每則最多 96 generated tokens。
- 模型只在有價值的標題類型觸發。
- `data/qwen_cache.json` 快取相同內容。
- 其他新聞使用透明事件規則。
- 全市場只更新名單；深度分析股票在 `config/stocks.json` 控制。

如果 GitHub Actions 過慢：

1. 手動執行時勾 `skip_qwen`。
2. 減少 `config/stocks.json` 深度股票數。
3. 確認 Hugging Face cache 有命中。
