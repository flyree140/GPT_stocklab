# 免費模型策略

## 為什麼不依賴 Hugging Face Serverless API

這個專案直接把模型下載到 GitHub Actions runner，避免每日分析受限於很小的免費推論額度。模型 inference 發生在 GitHub 執行環境，不在瀏覽器，也不需要 OpenAI、Gemini 或其他付費金鑰。

## 第一層：中文財經情緒

```text
bardsai/finance-sentiment-zh-fast
```

用途：

- 對所有去重後新聞判斷 positive / neutral / negative
- 提供分類信心
- 與透明詞典規則混合，避免只相信單一模型

特性：

- 約 0.1B 級別，適合 CPU 批次
- Model card 標示 Apache-2.0
- 財經文本特化

## 第二層：結構化事件解釋

```text
Qwen/Qwen3-0.6B
```

用途：

- 只處理每日高關聯新聞，不分析每一篇
- 輸出 category、horizon、mechanism、risk_factors
- 使用 `enable_thinking=False`、固定格式 JSON、無抽樣生成

特性：

- 約 0.6B，能在 GitHub CPU runner 運作，但速度依當日新聞量而異
- Model card 標示 Apache-2.0
- 多語言能力較適合中英文混合公司新聞

## 第三層：透明規則

無論模型是否安裝，規則引擎一定存在：

- 利多與利空詞彙權重
- 事件分類詞彙
- 影響期間規則
- 公司關聯性
- 來源品質
- 時效衰減

模型下載、載入或輸出格式失敗時，自動使用規則結果。

## 如何降低 GitHub 執行時間

- `QWEN_DAILY_LIMIT=8`：整天最多 8 則使用 Qwen。
- `qwen_max_news_per_stock=1`：每檔最多 1 則。
- Hugging Face cache：後續 Action 不必重複完整下載。
- 手動勾選 `skip_qwen`：保留小型分類器與規則。
- 股票清單先維持 10–20 檔，再逐步增加。

## Kaggle 選用

`notebooks/StockLab_Backfill_Kaggle.ipynb` 適合：

- 一次回填許多歷史日期
- 使用 Kaggle GPU 做較大批次
- 先產生 snapshots，再把 JSON 提交回 GitHub

Notebook 預設 `REVEAL=False`，不會自動下載切點後答案。

## 模型風險

- 小模型可能把否定句、反諷、條件式或產業術語判斷錯誤。
- 新聞正向不代表價格會上漲。
- 模型機制描述只可作為閱讀輔助，不是財務事實來源。
- 正式上線前應用歷史 walk-forward 資料做校準與分數分桶。
