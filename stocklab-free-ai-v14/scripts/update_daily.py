#!/usr/bin/env python3
"""Build the daily StockLab dataset with free data and local open-source models."""
from __future__ import annotations

import argparse
import logging
import math
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ai_analysis import HybridNewsAnalyzer
from common import ROOT, TAIPEI, clamp, configure_logging, iso_now, load_settings, load_stocks, read_json, write_json
from indicators import calculate as calculate_indicators
from market_sources import (
    fetch_institutional_map,
    fetch_material_information,
    fetch_price_history,
    fetch_revenue_map,
    fetch_taiex_snapshot,
    fetch_valuation_map,
)
from news_sources import fetch_news_for_stock
from scoring import (
    composite_scores,
    data_completeness,
    market_summary,
    recommendation,
    score_fundamental,
    score_institutional,
    score_news,
    score_risk,
    score_technical,
    select_top_picks,
)

LOGGER = logging.getLogger("stocklab.update")
DATA_DIR = ROOT / "data"


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _price_block(history: list[dict[str, Any]], as_of: date) -> dict[str, Any]:
    rows = [row for row in history if str(row.get("date", "")) <= as_of.isoformat()]
    if not rows:
        return {
            "date": None,
            "close": None,
            "previous_close": None,
            "change_pct": None,
            "currency": "TWD",
            "history": [],
            "source": "unavailable",
            "available_at": None,
        }
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else latest
    close = float(latest.get("close") or 0)
    previous_close = float(previous.get("close") or close)
    change_pct = (close / previous_close - 1) * 100 if previous_close else 0.0
    return {
        "date": latest.get("date"),
        "close": round(close, 4),
        "previous_close": round(previous_close, 4),
        "change_pct": round(change_pct, 3),
        "currency": "TWD",
        "history": rows,
        "source": latest.get("source", "free market source"),
        "available_at": latest.get("available_at") or latest.get("date"),
    }


def _fundamental_block(
    symbol: str,
    valuation: dict[str, dict[str, Any]],
    revenue: dict[str, dict[str, Any]],
    *,
    historical: bool,
) -> dict[str, Any]:
    # The public TWSE endpoints used here expose current snapshots. They are deliberately
    # excluded from retrospective runs because today's values would leak into the past.
    if historical:
        return {
            "period": None,
            "revenue": None,
            "revenue_yoy": None,
            "revenue_mom": None,
            "pe": None,
            "pb": None,
            "dividend_yield": None,
            "source": "omitted in retrospective mode (no archived point-in-time file)",
            "available_at": None,
        }
    revenue_row = revenue.get(symbol, {})
    valuation_row = valuation.get(symbol, {})
    sources = [row.get("source") for row in (revenue_row, valuation_row) if row.get("source")]
    fetched = [row.get("fetched_at") for row in (revenue_row, valuation_row) if row.get("fetched_at")]
    return {
        "period": revenue_row.get("period"),
        "revenue": revenue_row.get("revenue"),
        "revenue_yoy": revenue_row.get("revenue_yoy"),
        "revenue_mom": revenue_row.get("revenue_mom"),
        "pe": valuation_row.get("pe"),
        "pb": valuation_row.get("pb"),
        "dividend_yield": valuation_row.get("dividend_yield"),
        "source": " + ".join(dict.fromkeys(str(item) for item in sources)) or "unavailable",
        "available_at": max(fetched) if fetched else None,
    }


def _prediction(scores: dict[str, float]) -> dict[str, Any]:
    news = float(scores.get("news", 0))
    technical = float(scores.get("technical", 50))
    fundamental = float(scores.get("fundamental", 50))
    composite = float(scores.get("composite", 50))

    def logistic(x: float) -> float:
        return 1 / (1 + math.exp(-x))

    horizon_specs = [
        (1, (composite - 50) / 18 + news / 115 + (technical - 50) / 70),
        (5, (composite - 50) / 15 + news / 90 + (technical - 50) / 85),
        (20, (composite - 50) / 14 + news / 105 + (fundamental - 50) / 70),
    ]
    horizons = []
    for days, signal in horizon_specs:
        probability = clamp(logistic(signal), 0.08, 0.92)
        expected = clamp((probability - 0.5) * (2.2 if days == 1 else 5.0 if days == 5 else 9.0), -8, 8)
        horizons.append(
            {
                "trading_days": days,
                "up_probability": round(probability, 3),
                "expected_abnormal_return_pct": round(expected, 2),
                "direction": "up" if probability >= 0.55 else "down" if probability <= 0.45 else "neutral",
            }
        )
    return {
        "method": "calibratable-transparent-logistic-v1",
        "horizons": horizons,
        "note": "This is a point-in-time research forecast, not an actual outcome.",
    }


def _fallback_stock(previous: dict[str, Any] | None, stock: dict[str, Any], as_of: date, message: str) -> dict[str, Any]:
    if previous:
        copied = dict(previous)
        copied["stale"] = True
        copied["stale_reason"] = message
        copied["requested_as_of"] = as_of.isoformat()
        return copied
    return {
        "symbol": str(stock.get("symbol")),
        "market": stock.get("market", "TWSE"),
        "name": stock.get("name", stock.get("symbol")),
        "industry": stock.get("industry", ""),
        "price": _price_block([], as_of),
        "scores": {"news": 0, "technical": 50, "fundamental": 50, "institutional": 50, "risk": 100, "completeness": 0, "composite": 0},
        "recommendation": recommendation(0, 0, 100, 0),
        "prediction": _prediction({"news": 0, "technical": 50, "fundamental": 50, "composite": 0}),
        "technical": calculate_indicators([]),
        "fundamental": _fundamental_block(str(stock.get("symbol")), {}, {}, historical=True),
        "institutional": {},
        "news": [],
        "news_audit": {"weighted_items": 0, "positive": 0, "negative": 0, "average_relevance": 0},
        "stale": True,
        "stale_reason": message,
    }


def build_payload(
    *,
    as_of: date,
    historical: bool = False,
    enable_qwen: bool | None = None,
    write_files: bool = True,
) -> dict[str, Any]:
    settings = load_settings()
    stocks_config = load_stocks()
    if not stocks_config:
        raise RuntimeError("config/stocks.json contains no stocks")

    sentiment_enabled = _bool_env("ENABLE_HF_SENTIMENT", bool(settings.get("enable_sentiment_model", True)))
    qwen_enabled = _bool_env("ENABLE_QWEN", bool(settings.get("enable_qwen", True))) if enable_qwen is None else enable_qwen
    sentiment_name = os.getenv("SENTIMENT_MODEL", str(settings.get("sentiment_model")))
    llm_name = os.getenv("LLM_MODEL", str(settings.get("llm_model")))
    analyzer = HybridNewsAnalyzer(
        sentiment_model_name=sentiment_name,
        llm_model_name=llm_name,
        enable_sentiment=sentiment_enabled,
        enable_qwen=qwen_enabled,
    )

    previous_payload = read_json(DATA_DIR / "latest.json", {}) or {}
    previous_by_symbol = {str(row.get("symbol")): row for row in previous_payload.get("stocks", [])}

    if historical:
        valuation_map: dict[str, dict[str, Any]] = {}
        revenue_map: dict[str, dict[str, Any]] = {}
        material_rows: list[dict[str, Any]] = []
        taiex = None
    else:
        LOGGER.info("Fetching current TWSE fundamentals and material information")
        valuation_map = fetch_valuation_map()
        revenue_map = fetch_revenue_map()
        material_rows = fetch_material_information()
        taiex = fetch_taiex_snapshot()

    institutional_date, institutional_map = fetch_institutional_map(as_of)
    lookback_price = int(settings.get("price_lookback_days", 380))
    lookback_news = int(settings.get("historical_news_lookback_days" if historical else "news_lookback_days", 14 if historical else 7))
    max_news = int(settings.get("max_news_per_stock", 12))
    qwen_per_stock = int(settings.get("qwen_max_news_per_stock", 1))
    qwen_daily_budget = int(os.getenv("QWEN_DAILY_LIMIT", "8"))
    qwen_used = 0

    built: list[dict[str, Any]] = []
    for index, stock in enumerate(stocks_config, start=1):
        symbol = str(stock.get("symbol"))
        LOGGER.info("[%s/%s] Building %s %s", index, len(stocks_config), symbol, stock.get("name"))
        try:
            history = fetch_price_history(stock, as_of - timedelta(days=lookback_price), as_of)
            if not history:
                built.append(_fallback_stock(previous_by_symbol.get(symbol), stock, as_of, "No price history returned"))
                continue
            price = _price_block(history, as_of)
            technical = calculate_indicators(history)
            fundamental = _fundamental_block(symbol, valuation_map, revenue_map, historical=historical)
            institutional = institutional_map.get(symbol, {})

            raw_news = fetch_news_for_stock(
                stock,
                as_of,
                lookback_news,
                material_rows=material_rows,
                max_items=max_news,
            )
            raw_news.sort(
                key=lambda item: (
                    float(item.get("relevance", 0)),
                    float(item.get("source_quality", 0)),
                    str(item.get("published_at", "")),
                ),
                reverse=True,
            )
            analyzed_news: list[dict[str, Any]] = []
            for news_index, item in enumerate(raw_news):
                use_qwen = qwen_enabled and news_index < qwen_per_stock and qwen_used < qwen_daily_budget
                analyzed = analyzer.analyze(stock, item, use_qwen=use_qwen)
                if use_qwen and "qwen" in str(analyzed.get("analysis_method", "")).lower():
                    qwen_used += 1
                analyzed_news.append(analyzed)
            analyzed_news.sort(key=lambda item: str(item.get("published_at", "")), reverse=True)

            news_score, news_audit = score_news(analyzed_news, as_of)
            technical_score = score_technical(technical, price)
            fundamental_score = score_fundamental(fundamental)
            latest_volume = float(history[-1].get("volume") or 0)
            institutional_score = score_institutional(institutional, latest_volume)
            risk = score_risk(technical, fundamental, analyzed_news)
            completeness = data_completeness(history, technical, fundamental, institutional, analyzed_news)
            composite = composite_scores(
                news_score=news_score,
                technical_score=technical_score,
                fundamental_score=fundamental_score,
                institutional_score=institutional_score,
                risk_score=risk,
                completeness=completeness,
                weights=settings.get("score_weights"),
            )
            scores = {
                "news": news_score,
                "technical": technical_score,
                "fundamental": fundamental_score,
                "institutional": institutional_score,
                "risk": risk,
                "completeness": completeness,
                "composite": composite,
            }
            built.append(
                {
                    "symbol": symbol,
                    "market": stock.get("market", "TWSE"),
                    "name": stock.get("name", symbol),
                    "industry": stock.get("industry", ""),
                    "price": price,
                    "scores": scores,
                    "recommendation": recommendation(composite, news_score, risk, completeness),
                    "prediction": _prediction(scores),
                    "technical": technical,
                    "fundamental": fundamental,
                    "institutional": institutional,
                    "news": analyzed_news,
                    "news_audit": news_audit,
                    "stale": False,
                }
            )
        except Exception as exc:
            LOGGER.exception("Failed to build %s", symbol)
            built.append(_fallback_stock(previous_by_symbol.get(symbol), stock, as_of, str(exc)))

    built.sort(key=lambda item: float(item.get("scores", {}).get("composite", 0)), reverse=True)
    if not any(item.get("price", {}).get("close") is not None for item in built):
        raise RuntimeError("No stock had usable price data; refusing to overwrite data files")

    top_picks = select_top_picks(built, settings)
    market = market_summary(built)
    market["taiex"] = taiex
    generated_at = iso_now()
    mode = "retrospective" if historical else "live"
    payload = {
        "schema_version": "2.0",
        "generated_at": generated_at,
        "as_of": as_of.isoformat(),
        "timezone": str(settings.get("timezone", "Asia/Taipei")),
        "mode": mode,
        "snapshot_type": "retrospective_point_in_time" if historical else "daily_point_in_time",
        "retrospective": historical,
        "disclaimer": "Research tool only. Not investment advice. Free sources and small open models can be delayed or wrong.",
        "model": {
            "sentiment": sentiment_name,
            "sentiment_enabled": sentiment_enabled,
            "llm": llm_name,
            "llm_enabled": qwen_enabled,
            "llm_items_analyzed": qwen_used,
            "fallback": str(settings.get("fallback_model", "transparent-rule-v2")),
            "license_note": "Configured models use permissive open-source licenses; verify model cards before redistribution.",
        },
        "market": market,
        "top_picks": top_picks,
        "stocks": built,
        "audit": {
            "cutoff": as_of.isoformat(),
            "future_fields_present": False,
            "institutional_data_date": institutional_date,
            "historical_current_fundamentals_omitted": historical,
            "timeline": [
                {
                    "time": as_of.isoformat(),
                    "label": "資料切點",
                    "detail": "published_at、available_at 與價格日期不得晚於此日。",
                },
                {
                    "time": generated_at,
                    "label": "快照產生",
                    "detail": "回溯快照可以晚於切點建立，但不包含切點後答案。",
                },
            ],
        },
    }

    if write_files:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path = DATA_DIR / "snapshots" / f"{as_of.isoformat()}.json"
        write_json(snapshot_path, payload)
        if not historical:
            write_json(DATA_DIR / "latest.json", payload)
        _update_manifest(as_of, historical, generated_at)
        LOGGER.info("Wrote %s", snapshot_path)
    return payload


def _update_manifest(as_of: date, historical: bool, generated_at: str) -> None:
    manifest_path = DATA_DIR / "manifest.json"
    manifest = read_json(manifest_path, {}) or {}
    snapshots = [row for row in manifest.get("snapshots", []) if row.get("date") != as_of.isoformat()]
    snapshots.append(
        {
            "date": as_of.isoformat(),
            "label": "歷史回溯（不含答案）" if historical else "每日鎖定快照",
            "path": f"./data/snapshots/{as_of.isoformat()}.json",
            "reveal_available": (DATA_DIR / "results" / f"{as_of.isoformat()}.json").exists(),
        }
    )
    snapshots.sort(key=lambda row: str(row.get("date", "")), reverse=True)
    write_json(
        manifest_path,
        {
            "schema_version": "1.0",
            "updated_at": generated_at,
            "latest": "./data/latest.json",
            "snapshots": snapshots[:400],
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="Point-in-time cutoff, YYYY-MM-DD. Defaults to today in Asia/Taipei.")
    parser.add_argument("--historical", action="store_true", help="Strict retrospective mode; current-only fundamentals are omitted.")
    parser.add_argument("--skip-qwen", action="store_true", help="Use finance classifier + transparent rules only.")
    parser.add_argument("--no-write", action="store_true", help="Build in memory without modifying data files.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    cutoff = date.fromisoformat(args.as_of) if args.as_of else datetime.now(tz=TAIPEI).date()
    historical = args.historical or cutoff < datetime.now(tz=TAIPEI).date() - timedelta(days=2)
    build_payload(
        as_of=cutoff,
        historical=historical,
        enable_qwen=False if args.skip_qwen else None,
        write_files=not args.no_write,
    )


if __name__ == "__main__":
    main()
