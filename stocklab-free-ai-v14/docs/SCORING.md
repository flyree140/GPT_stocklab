# 新聞與綜合評分

## 單一新聞

模型輸出 `impact_score ∈ [-100, 100]`，但不直接等同股價漲跌幅。

單則事件權重：

```text
weight = confidence × company_relevance × source_quality × recency_decay
```

時效衰減：

```text
recency_decay = exp(-新聞年齡天數 / 5)
```

股票新聞分：

```text
raw_news = Σ(impact_score × weight) / Σ(weight)
news_score = raw_news × evidence_factor
```

`evidence_factor` 會隨去重後的有效事件數增加，但上限為 1，避免單篇低信心文章被誤當成強訊號。

## 綜合分

預設權重在 `config/settings.json`：

```text
composite = 50
  + news_score × 0.33
  + (technical - 50) × 0.24
  + (fundamental - 50) × 0.15
  + (institutional - 50) × 0.10
  + (completeness - 50) × 0.08
  - risk × 0.18
```

最後限制在 `0～100`。

## 技術分

以可解釋的條件加減分：

- 收盤價相對 SMA 5/20/60
- SMA 5 與 SMA 20 相對位置
- MACD histogram 正負
- RSI 是否處於健康趨勢、超買或極弱區
- 放量上漲或放量下跌

## 基本分

免費版本目前主要使用：

- 月營收年增與月增
- 本益比
- 股價淨值比
- 殖利率

不同產業不應用完全相同估值尺度。這一版先提供通用基準；正式研究可在股票設定中加入產業分群與分位數。

## 籌碼分

三大法人淨買賣超會以當日成交量標準化，避免大型股與小型股直接用張數比較。外資與投信同向時加分，反向時不強迫做單一結論。

## 風險分

風險越高越差，包含：

- ATR 百分比
- RSI 過熱
- 高估值
- 嚴重負面事件數
- 低品質新聞來源比例

## 資料完整度

價格、技術、基本、籌碼、新聞分別有權重。缺資料不會被自動視為中性好消息；它會降低完整度，進而減少綜合分與置頂資格。

## 每日置頂

預設需同時滿足：

```text
composite >= 55
completeness >= 58
risk <= 72
average_news_relevance >= 0.55（有新聞時）
stale == false
```

再依綜合分、新聞分與完整度排序，最多五檔。候選不足時就少顯示；系統不會為了湊滿五檔而繞過門檻。
