#!/usr/bin/env python3
"""Fast offline quality checks for generated static artifacts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from common import ROOT, read_json
from validate_no_leak import validate_snapshot


def main() -> None:
    errors: list[str] = []
    required = [
        ROOT / "index.html",
        ROOT / "assets" / "app.js",
        ROOT / "assets" / "styles.css",
        ROOT / "data" / "latest.json",
        ROOT / "data" / "manifest.json",
        ROOT / "config" / "stocks.json",
        ROOT / "config" / "settings.json",
    ]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing or empty: {path.relative_to(ROOT)}")
    for path in ROOT.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")
    try:
        subprocess.run(["node", "--check", str(ROOT / "assets" / "app.js")], check=True, capture_output=True, text=True)
    except Exception as exc:
        errors.append(f"JavaScript syntax check failed: {exc}")
    manifest = read_json(ROOT / "data" / "manifest.json", {}) or {}
    for row in manifest.get("snapshots", []):
        path = ROOT / str(row.get("path", "")).replace("./", "")
        if not path.exists():
            errors.append(f"manifest snapshot missing: {path.relative_to(ROOT)}")
            continue
        snapshot = read_json(path, {})
        leak_errors = validate_snapshot(snapshot)
        errors.extend(f"{path.name}: {message}" for message in leak_errors)
    if errors:
        print("QUALITY CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("QUALITY CHECK PASSED")


if __name__ == "__main__":
    main()
