# 資料格式摘要

## `data/latest.json`

```json
{
  "as_of": "2026-08-28",
  "generated_at": "...",
  "mode": "live",
  "model": {},
  "market": {},
  "top_picks": ["2330", "2317"],
  "stocks": []
}
```

## Stock

```json
{
  "symbol": "2330",
  "name": "台積電",
  "price": {"date": "...", "close": 0, "history": []},
  "scores": {
    "news": 0,
    "technical": 0,
    "fundamental": 0,
    "institutional": 0,
    "risk": 0,
    "completeness": 0,
    "composite": 0
  },
  "recommendation": {},
  "prediction": {"horizons": []},
  "technical": {},
  "fundamental": {},
  "institutional": {},
  "news": [],
  "news_audit": {}
}
```

## News

```json
{
  "title": "...",
  "source": "...",
  "url": "...",
  "published_at": "...",
  "available_at": "...",
  "fetched_at": "...",
  "sentiment": "positive",
  "impact_score": 35,
  "confidence": 0.78,
  "horizon": "5–20 個交易日",
  "category": "營收與需求",
  "mechanism": "...",
  "risk_factors": [],
  "source_quality": 0.9,
  "relevance": 1.0,
  "model_version": "..."
}
```

Schema 版本目前為 `2.0`。前端對缺欄位採容錯顯示，日後可逐步增加資料。
