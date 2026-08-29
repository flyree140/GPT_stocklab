#!/usr/bin/env python3
"""Create a strict historical snapshot and, only on explicit request, reveal outcomes."""
from __future__ import annotations

import argparse
import math
from datetime import date, timedelta
from typing import Any

from common import ROOT, configure_logging, load_settings, load_stocks, read_json, write_json
from market_sources import fetch_price_history
from update_daily import build_payload
from validate_no_leak import validate_snapshot


def _horizon_return(history: list[dict[str, Any]], cutoff: date, base_close: float, trading_days: int) -> tuple[str | None, float | None, float | None]:
    future = [row for row in history if str(row.get("date", "")) > cutoff.isoformat()]
    if len(future) < trading_days:
        return None, None, None
    row = future[trading_days - 1]
    close = float(row.get("close") or 0)
    result = (close / base_close - 1) * 100 if base_close else None
    return str(row.get("date")), close, result


def _brier(probability: float, outcome_up: bool) -> float:
    return (probability - (1.0 if outcome_up else 0.0)) ** 2


def reveal(as_of: date) -> dict[str, Any]:
    snapshot_path = ROOT / "data" / "snapshots" / f"{as_of.isoformat()}.json"
    snapshot = read_json(snapshot_path, {})
    if not snapshot:
        raise RuntimeError(f"Snapshot not found: {snapshot_path}")
    errors = validate_snapshot(snapshot, as_of)
    if errors:
        raise RuntimeError("Snapshot failed no-leak validation: " + "; ".join(errors))

    settings = load_settings()
    stock_configs = {str(item.get("symbol")): item for item in load_stocks()}
    horizons = [int(value) for value in settings.get("validation_horizons", [1, 5, 20])]
    max_horizon = max(horizons)
    end = as_of + timedelta(days=max_horizon * 3 + 25)
    result_rows: list[dict[str, Any]] = []

    for stock in snapshot.get("stocks", []):
        symbol = str(stock.get("symbol"))
        config = stock_configs.get(symbol, {"symbol": symbol, "market": stock.get("market", "TWSE")})
        base_close = float(stock.get("price", {}).get("close") or 0)
        history = fetch_price_history(config, as_of - timedelta(days=5), end)
        predicted = {int(row.get("trading_days")): row for row in stock.get("prediction", {}).get("horizons", [])}
        outcomes = []
        for horizon in horizons:
            actual_date, actual_close, actual_return = _horizon_return(history, as_of, base_close, horizon)
            forecast = predicted.get(horizon, {})
            probability = float(forecast.get("up_probability", 0.5))
            direction = str(forecast.get("direction", "neutral"))
            hit = None
            brier = None
            if actual_return is not None:
                actual_up = actual_return > 0
                hit = (direction == "up" and actual_up) or (direction == "down" and not actual_up) or (direction == "neutral" and abs(actual_return) < 1)
                brier = _brier(probability, actual_up)
            outcomes.append(
                {
                    "trading_days": horizon,
                    "forecast": forecast,
                    "actual_date": actual_date,
                    "actual_close": actual_close,
                    "actual_return_pct": round(actual_return, 3) if actual_return is not None else None,
                    "direction_hit": hit,
                    "brier_score": round(brier, 4) if brier is not None else None,
                }
            )
        result_rows.append(
            {
                "symbol": symbol,
                "name": stock.get("name"),
                "base_date": stock.get("price", {}).get("date"),
                "base_close": base_close,
                "outcomes": outcomes,
            }
        )

    flat = [outcome for row in result_rows for outcome in row["outcomes"] if outcome.get("actual_return_pct") is not None]
    hits = [bool(item["direction_hit"]) for item in flat if item.get("direction_hit") is not None]
    briers = [float(item["brier_score"]) for item in flat if item.get("brier_score") is not None]
    returns = [float(item["actual_return_pct"]) for item in flat]
    result = {
        "schema_version": "1.0",
        "as_of": as_of.isoformat(),
        "revealed": True,
        "separate_from_snapshot": True,
        "summary": {
            "stocks": len(result_rows),
            "observations": len(flat),
            "direction_accuracy_pct": round(sum(hits) / len(hits) * 100, 2) if hits else None,
            "mean_brier_score": round(sum(briers) / len(briers), 4) if briers else None,
            "mean_return_pct": round(sum(returns) / len(returns), 3) if returns else None,
            "note": "This result file was generated only after an explicit reveal request.",
        },
        "stocks": result_rows,
    }
    result_path = ROOT / "data" / "results" / f"{as_of.isoformat()}.json"
    write_json(result_path, result)

    manifest_path = ROOT / "data" / "manifest.json"
    manifest = read_json(manifest_path, {}) or {}
    for row in manifest.get("snapshots", []):
        if row.get("date") == as_of.isoformat():
            row["reveal_available"] = True
    write_json(manifest_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="Historical cutoff YYYY-MM-DD")
    parser.add_argument("--reveal", action="store_true", help="Explicitly download post-cutoff prices and create a separate result file")
    parser.add_argument("--skip-qwen", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    configure_logging(args.verbose)
    cutoff = date.fromisoformat(args.as_of)
    snapshot = build_payload(as_of=cutoff, historical=True, enable_qwen=not args.skip_qwen, write_files=True)
    errors = validate_snapshot(snapshot, cutoff)
    if errors:
        raise RuntimeError("No-leak validation failed: " + "; ".join(errors))
    print(f"Snapshot created without outcomes: data/snapshots/{cutoff.isoformat()}.json")
    if args.reveal:
        result = reveal(cutoff)
        print(f"Result revealed separately: {result['summary']}")
    else:
        print("No result file was generated. Use --reveal only after you choose to see the answer.")


if __name__ == "__main__":
    main()
