#!/usr/bin/env python3
"""Validate that a point-in-time snapshot contains no post-cutoff answers or dates."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from common import ROOT, date_not_after, parse_iso_datetime, read_json

FORBIDDEN_EXACT = {
    "actual_return",
    "actual_returns",
    "actual_abnormal_return",
    "future_return",
    "future_price",
    "outcome",
    "realized_return",
    "direction_hit",
    "hit",
    "answer",
    "label_after_cutoff",
}
FORBIDDEN_FRAGMENTS = ("post_cutoff", "after_cutoff_price", "realized_outcome")
DATE_KEYS = {"date", "published_at", "available_at"}
IGNORE_DATE_PATH_PARTS = {"generated_at", "fetched_at", "updated_at"}


def validate_snapshot(payload: dict[str, Any], cutoff: date | None = None) -> list[str]:
    errors: list[str] = []
    cutoff = cutoff or date.fromisoformat(str(payload.get("as_of")))
    if str(payload.get("as_of")) != cutoff.isoformat():
        errors.append(f"root.as_of is {payload.get('as_of')}, expected {cutoff.isoformat()}")

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                child_path = f"{path}.{key}" if path else str(key)
                if lowered in FORBIDDEN_EXACT or any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
                    errors.append(f"forbidden future-answer field: {child_path}")
                if lowered in DATE_KEYS and not any(part in child_path for part in IGNORE_DATE_PATH_PARTS):
                    if isinstance(child, str) and child and not date_not_after(child, cutoff):
                        errors.append(f"post-cutoff date at {child_path}: {child}")
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(payload, "root")
    result_path = ROOT / "data" / "results" / f"{cutoff.isoformat()}.json"
    # A result file may exist separately, but it must never be embedded or referenced as loaded by default.
    if payload.get("result") is not None or payload.get("results") is not None:
        errors.append("snapshot embeds a result/results field")
    if payload.get("audit", {}).get("future_fields_present") not in {False, None}:
        errors.append("audit.future_fields_present is not false")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Snapshot JSON path")
    parser.add_argument("--as-of", help="Cutoff YYYY-MM-DD; defaults to payload.as_of")
    args = parser.parse_args()
    path = Path(args.path) if args.path else ROOT / "data" / "snapshots" / "2025-08-15.json"
    payload = read_json(path, {})
    cutoff = date.fromisoformat(args.as_of) if args.as_of else None
    errors = validate_snapshot(payload, cutoff)
    if errors:
        print("NO-LEAK VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"NO-LEAK VALIDATION PASSED: {path}")


if __name__ == "__main__":
    main()
