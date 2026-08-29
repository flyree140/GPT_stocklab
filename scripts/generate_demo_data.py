#!/usr/bin/env python3
"""Generate deterministic, clearly labeled synthetic data for the first page load.

`latest.json` uses a recent demo date so the interface is easy to inspect before the first
GitHub Actions run. A separate 2025-08-15 snapshot demonstrates strict point-in-time mode.
No result/outcome field is written anywhere.
"""
from __future__ import annotations

import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
TAIPEI = ZoneInfo("Asia/Taipei")
CURRENT_AS_OF = date(2026, 8, 28)
HISTORICAL_CUTOFF = date(2025, 8, 15)
GENERATED_AT = "2026-08-29T12:00:00+08:00"

STOCKS = [
    ("2330", "台積電", "半導體", 42),
    ("2317", "鴻海", "其他電子", 37),
    ("2454", "聯發科", "半導體", 34),
    ("2382", "廣達", "電腦及週邊", 31),
    ("2308", "台達電", "電子零組件", 29),
    ("2881", "富邦金", "金融保險", 18),
    ("2882", "國泰金", "金融保險", 16),
    ("2412", "中華電", "通信網路", 12),
    ("3711", "日月光投控", "半導體", 24),
]

BASE_PRICES = {
    "2330": 1130,
    "2317": 205,
    "2454": 1450,
    "2382": 290,
    "2308": 430,
    "2881": 91,
    "2882": 69,
    "2412": 128,
    "3711": 168,
}


def business_days(end: date, count: int) -> list[date]:
    days: list[date] = []
    current = end
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current -= timedelta(days=1)
    return list(reversed(days))


def history(seed: int, base: float, as_of: date) -> list[dict[str, object]]:
    rng = random.Random(seed + as_of.toordinal())
    value = base * 0.88
    rows = []
    for idx, day in enumerate(business_days(as_of, 90)):
        drift = 0.0012 + math.sin(idx / 8) * 0.002
        shock = rng.uniform(-0.018, 0.018)
        value = max(10, value * (1 + drift + shock))
        high = value * (1 + rng.uniform(0.002, 0.014))
        low = value * (1 - rng.uniform(0.002, 0.014))
        rows.append(
            {
                "date": day.isoformat(),
                "open": round((high + low) / 2 * rng.uniform(0.995, 1.005), 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(value, 2),
                "volume": int(rng.uniform(8_000_000, 45_000_000)),
                "source": "synthetic-demo",
                "available_at": day.isoformat(),
            }
        )
    return rows


def prediction(composite: float, news_score: float) -> dict[str, object]:
    rows = []
    for days, scale in ((1, 0.65), (5, 1.0), (20, 1.3)):
        probability = max(0.08, min(0.92, 0.5 + (composite - 50) / 160 * scale + news_score / 650))
        rows.append(
            {
                "trading_days": days,
                "up_probability": round(probability, 3),
                "expected_abnormal_return_pct": round((probability - 0.5) * (2.2 if days == 1 else 5 if days == 5 else 9), 2),
                "direction": "up" if probability >= 0.55 else "down" if probability <= 0.45 else "neutral",
            }
        )
    return {"method": "synthetic-demo", "horizons": rows, "note": "Demo forecast only; no outcome is included."}


def make_stock(symbol: str, name: str, industry: str, seed: int, rank: int, as_of: date) -> dict[str, object]:
    rng = random.Random(seed + as_of.toordinal())
    price_history = history(seed, BASE_PRICES[symbol], as_of)
    close = float(price_history[-1]["close"])
    previous = float(price_history[-2]["close"])
    change_pct = (close / previous - 1) * 100

    news_score = max(-100, min(100, 72 - rank * 8 + rng.randint(-8, 8)))
    technical = max(0, min(100, 78 - rank * 5 + rng.randint(-7, 7)))
    fundamental = max(0, min(100, 82 - rank * 4 + rng.randint(-5, 5)))
    institutional = max(0, min(100, 68 - rank * 3 + rng.randint(-12, 12)))
    risk = max(8, min(92, 26 + rank * 4 + rng.randint(-5, 6)))
    completeness = max(54, min(96, 93 - rank * 3))
    composite = round(
        50
        + news_score * 0.33
        + (technical - 50) * 0.24
        + (fundamental - 50) * 0.15
        + (institutional - 50) * 0.10
        + (completeness - 50) * 0.08
        - risk * 0.18,
        1,
    )
    composite = max(0, min(100, composite))

    ma5 = sum(float(row["close"]) for row in price_history[-5:]) / 5
    ma20 = sum(float(row["close"]) for row in price_history[-20:]) / 20
    ma60 = sum(float(row["close"]) for row in price_history[-60:]) / 60
    rsi = max(18, min(82, 64 - rank * 3 + rng.randint(-8, 8)))
    foreign_net = int((7 - rank) * rng.uniform(450_000, 2_100_000))
    trust_net = int((5 - rank) * rng.uniform(120_000, 650_000))
    dealer_net = int(rng.uniform(-500_000, 500_000))

    direction = "positive" if composite >= 62 else "neutral" if composite >= 45 else "negative"
    label = "偏多研究" if direction == "positive" else "中性觀察" if direction == "neutral" else "風險偏高"
    news_date_1 = as_of - timedelta(days=1)
    news_date_2 = as_of - timedelta(days=2)
    news = [
        {
            "id": f"demo-{as_of}-{symbol}-1",
            "title": f"【示範】{name}公布營運更新，市場關注需求與獲利能力",
            "description": "此內容為介面展示用合成資料，不代表真實新聞。",
            "source": "示範資料",
            "url": "",
            "published_at": f"{news_date_1.isoformat()}T09:20:00+08:00",
            "available_at": f"{news_date_1.isoformat()}T09:20:00+08:00",
            "fetched_at": GENERATED_AT,
            "sentiment": "positive" if rank < 6 else "neutral",
            "impact_score": int(max(-20, 58 - rank * 7)),
            "confidence": round(max(0.51, 0.87 - rank * 0.035), 2),
            "horizon": "5–20 個交易日",
            "category": "營收與需求",
            "mechanism": "若訂單與產品組合改善，可能提高營收能見度與獲利預期；若需求遞延，正向效果會減弱。",
            "risk_factors": ["市場已提前反映", "需求不如預期"],
            "source_quality": 0.72,
            "relevance": 0.92,
            "is_material_info": False,
            "analysis_method": "demo-hybrid-v2",
            "model_version": "demo-hybrid-v2",
        },
        {
            "id": f"demo-{as_of}-{symbol}-2",
            "title": f"【示範】{name}董事會通過重要議案，後續執行進度待觀察",
            "description": "此內容為介面展示用合成資料，不代表真實重大訊息。",
            "source": "示範官方重訊",
            "url": "",
            "published_at": f"{news_date_2.isoformat()}T17:40:00+08:00",
            "available_at": f"{news_date_2.isoformat()}T17:40:00+08:00",
            "fetched_at": GENERATED_AT,
            "sentiment": "neutral",
            "impact_score": int(rng.randint(-8, 18)),
            "confidence": 0.64,
            "horizon": "1–5 個交易日",
            "category": "公司治理",
            "mechanism": "議案不一定立即改變獲利，需等待金額、執行時程與資本配置的實際影響。",
            "risk_factors": ["資訊尚不完整"],
            "source_quality": 0.95,
            "relevance": 1.0,
            "is_material_info": True,
            "analysis_method": "demo-hybrid-v2",
            "model_version": "demo-hybrid-v2",
        },
    ]

    return {
        "symbol": symbol,
        "market": "TWSE",
        "name": name,
        "industry": industry,
        "price": {
            "date": as_of.isoformat(),
            "close": close,
            "previous_close": previous,
            "change_pct": round(change_pct, 2),
            "currency": "TWD",
            "history": price_history,
            "source": "synthetic-demo",
            "available_at": as_of.isoformat(),
        },
        "scores": {
            "news": news_score,
            "technical": technical,
            "fundamental": fundamental,
            "institutional": institutional,
            "risk": risk,
            "completeness": completeness,
            "composite": round(composite, 1),
        },
        "recommendation": {
            "direction": direction,
            "label": label,
            "reason": "示範排序顯示新聞與傳統面訊號的相對位置；正式資料會在首次 GitHub Action 後取代。",
            "risks": ["示範資料不可交易", "模型可能誤判", "市場價格可能提前反映"],
        },
        "prediction": prediction(composite, news_score),
        "technical": {
            "ma5": round(ma5, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "ema12": round(ma5 * 0.995, 2),
            "ema26": round(ma20 * 0.99, 2),
            "rsi14": round(rsi, 1),
            "macd": round((ma5 - ma20) * 0.22, 2),
            "macd_signal": round((ma5 - ma20) * 0.16, 2),
            "macd_hist": round((ma5 - ma20) * 0.06, 2),
            "k": round(max(10, min(90, rsi + 5)), 1),
            "d": round(max(10, min(90, rsi + 1)), 1),
            "atr": round(close * (0.018 + rank * 0.001), 2),
            "atr_pct": round(1.8 + rank * 0.1, 2),
            "volume_ratio": round(1.75 - rank * 0.08, 2),
            "support_20": round(min(float(row["close"]) for row in price_history[-20:]), 2),
            "resistance_20": round(max(float(row["close"]) for row in price_history[-20:]), 2),
        },
        "fundamental": {
            "period": f"{as_of.year}-{max(1, as_of.month - 1):02d}",
            "revenue": int(rng.uniform(18, 250) * 1_000_000_000),
            "revenue_yoy": round(28 - rank * 3.2, 1),
            "revenue_mom": round(8 - rank * 1.1, 1),
            "pe": round(17 + rank * 1.7, 2),
            "pb": round(2.0 + rank * 0.22, 2),
            "dividend_yield": round(4.2 - rank * 0.24, 2),
            "source": "synthetic-demo / TWSE schema",
            "available_at": (as_of - timedelta(days=4)).isoformat(),
        },
        "institutional": {
            "date": as_of.isoformat(),
            "foreign_net": foreign_net,
            "investment_trust_net": trust_net,
            "dealer_net": dealer_net,
            "total_net": foreign_net + trust_net + dealer_net,
            "source": "synthetic-demo / T86 schema",
            "available_at": f"{as_of.isoformat()}T15:30:00+08:00",
        },
        "news": news,
        "news_audit": {
            "weighted_items": len(news),
            "positive": sum(1 for item in news if item["impact_score"] > 15),
            "negative": sum(1 for item in news if item["impact_score"] < -15),
            "average_relevance": round(sum(float(item["relevance"]) for item in news) / len(news), 3),
        },
        "stale": False,
    }


def build_payload(as_of: date, retrospective: bool) -> dict[str, object]:
    stocks = [make_stock(*row, rank=index, as_of=as_of) for index, row in enumerate(STOCKS)]
    stocks.sort(key=lambda item: float(item["scores"]["composite"]), reverse=True)
    top = [str(item["symbol"]) for item in stocks[:5] if float(item["scores"]["completeness"]) >= 60]
    all_news = [news for stock in stocks for news in stock["news"]]
    positive = sum(1 for item in all_news if float(item["impact_score"]) > 15)
    negative = sum(1 for item in all_news if float(item["impact_score"]) < -15)
    completeness = sorted(float(item["scores"]["completeness"]) for item in stocks)
    return {
        "schema_version": "2.0",
        "generated_at": GENERATED_AT,
        "as_of": as_of.isoformat(),
        "timezone": "Asia/Taipei",
        "mode": "demo",
        "snapshot_type": "retrospective_point_in_time" if retrospective else "daily_point_in_time_demo",
        "retrospective": retrospective,
        "disclaimer": "Synthetic demo data. The first live GitHub Action replaces latest.json. Not investment advice.",
        "model": {
            "sentiment": "bardsai/finance-sentiment-zh-fast",
            "sentiment_enabled": False,
            "llm": "Qwen/Qwen3-0.6B",
            "llm_enabled": False,
            "llm_items_analyzed": 0,
            "fallback": "transparent-rule-v2",
            "license_note": "Demo metadata only; no model inference was run for synthetic rows.",
        },
        "market": {
            "news_temperature": 61,
            "sentiment_label": "positive",
            "positive_news": positive,
            "negative_news": negative,
            "median_completeness": completeness[len(completeness) // 2],
            "taiex": None,
        },
        "top_picks": top,
        "stocks": stocks,
        "audit": {
            "cutoff": as_of.isoformat(),
            "future_fields_present": False,
            "historical_current_fundamentals_omitted": False,
            "timeline": [
                {"time": (as_of - timedelta(days=4)).isoformat(), "label": "示範基本面可用", "detail": "所有日期均早於資料切點。"},
                {"time": (as_of - timedelta(days=2)).isoformat(), "label": "示範事件可用", "detail": "內容為合成資料並有清楚標示。"},
                {"time": as_of.isoformat(), "label": "快照鎖定", "detail": "不含此日之後的價格或答案欄位。"},
            ],
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "snapshots").mkdir(parents=True, exist_ok=True)
    (OUT / "results").mkdir(parents=True, exist_ok=True)
    latest = build_payload(CURRENT_AS_OF, retrospective=False)
    historical = build_payload(HISTORICAL_CUTOFF, retrospective=True)
    (OUT / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "snapshots" / f"{CURRENT_AS_OF}.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "snapshots" / f"{HISTORICAL_CUTOFF}.json").write_text(json.dumps(historical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "updated_at": GENERATED_AT,
        "latest": "./data/latest.json",
        "snapshots": [
            {"date": CURRENT_AS_OF.isoformat(), "label": "最新介面示範（合成資料）", "path": f"./data/snapshots/{CURRENT_AS_OF}.json", "reveal_available": False},
            {"date": HISTORICAL_CUTOFF.isoformat(), "label": "2025-08-15 無未來答案示範", "path": f"./data/snapshots/{HISTORICAL_CUTOFF}.json", "reveal_available": False},
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "results" / ".gitkeep").write_text("", encoding="utf-8")
    print(f"Wrote current and historical demo data to {OUT}")


if __name__ == "__main__":
    main()
