#!/usr/bin/env python3
"""Fast offline quality checks for generated static artifacts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from common import ROOT, read_json
from validate_no_leak import validate_snapshot


JSON_ROOTS = [
    ROOT / "data",
    ROOT / "config",
]

IGNORE_DIRS = {
    ".git",
    ".cache",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
}


def should_ignore(path: Path) -> bool:
    """Return True when a path belongs to a generated/cache directory."""
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return True

    return any(part in IGNORE_DIRS for part in relative.parts)


def collect_project_json_files() -> list[Path]:
    """
    Only validate JSON files that belong to StockLab itself.

    Do NOT scan the entire repository because external caches such as
    Hugging Face may contain JSON-like files, symlinks, incomplete cache
    artifacts, or metadata that should not be treated as application data.
    """
    files: list[Path] = []

    for json_root in JSON_ROOTS:
        if not json_root.exists():
            continue

        for path in json_root.rglob("*.json"):
            if path.is_file() and not should_ignore(path):
                files.append(path)

    return sorted(set(files))


def validate_json_file(path: Path) -> str | None:
    """Validate one UTF-8 JSON file and return an error string if invalid."""
    try:
        text = path.read_text(encoding="utf-8")

        if not text.strip():
            return f"empty JSON: {path.relative_to(ROOT)}"

        json.loads(text)
        return None

    except Exception as exc:
        return f"invalid JSON {path.relative_to(ROOT)}: {exc}"


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

    print("=== Required files ===")

    for path in required:
        if not path.exists():
            errors.append(f"missing: {path.relative_to(ROOT)}")
            continue

        if path.stat().st_size == 0:
            errors.append(f"empty: {path.relative_to(ROOT)}")
            continue

        print(f"OK  {path.relative_to(ROOT)}")

    print()
    print("=== Project JSON validation ===")

    json_files = collect_project_json_files()

    if not json_files:
        errors.append("no project JSON files found under data/ or config/")
    else:
        for path in json_files:
            error = validate_json_file(path)

            if error:
                errors.append(error)
            else:
                print(f"OK  {path.relative_to(ROOT)}")

    print()
    print("=== JavaScript syntax ===")

    try:
        result = subprocess.run(
            ["node", "--check", str(ROOT / "assets" / "app.js")],
            check=True,
            capture_output=True,
            text=True,
        )

        if result.stdout.strip():
            print(result.stdout.strip())

        print("OK  assets/app.js")

    except FileNotFoundError:
        errors.append("JavaScript syntax check failed: node executable not found")

    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        errors.append(f"JavaScript syntax check failed: {detail}")

    except Exception as exc:
        errors.append(f"JavaScript syntax check failed: {exc}")

    print()
    print("=== No-leak snapshot validation ===")

    manifest = read_json(ROOT / "data" / "manifest.json", {}) or {}

    snapshots = manifest.get("snapshots", [])

    if not isinstance(snapshots, list):
        errors.append("data/manifest.json: snapshots must be a list")
        snapshots = []

    for row in snapshots:
        if not isinstance(row, dict):
            errors.append("data/manifest.json: invalid snapshot row")
            continue

        snapshot_path = str(row.get("path", "")).strip()

        if not snapshot_path:
            errors.append("data/manifest.json: snapshot row missing path")
            continue

        path = ROOT / snapshot_path.replace("./", "")

        if not path.exists():
            errors.append(
                f"manifest snapshot missing: {path.relative_to(ROOT)}"
            )
            continue

        snapshot = read_json(path, {})

        if not isinstance(snapshot, dict):
            errors.append(f"{path.name}: snapshot root must be an object")
            continue

        leak_errors = validate_snapshot(snapshot)

        if leak_errors:
            errors.extend(
                f"{path.name}: {message}"
                for message in leak_errors
            )
        else:
            print(f"OK  {path.relative_to(ROOT)}")

    print()

    if errors:
        print("QUALITY CHECK FAILED")

        for error in errors:
            print(f"- {error}")

        raise SystemExit(1)

    print("QUALITY CHECK PASSED")


if __name__ == "__main__":
    main()
