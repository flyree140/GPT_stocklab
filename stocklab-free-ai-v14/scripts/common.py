"""Shared helpers for the StockLab free data pipeline."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import tempfile
import time
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

TAIPEI = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("stocklab")


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def now_taipei() -> datetime:
    return datetime.now(tz=TAIPEI)


def iso_now() -> str:
    return now_taipei().isoformat(timespec="seconds")


def parse_number(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "--", "---", "N/A", "nan", "null", "None"}:
        return default
    text = text.replace("＋", "+").replace("－", "-")
    try:
        return float(text)
    except ValueError:
        return default


def parse_int(value: Any, default: int | None = None) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(*parts: str) -> str:
    raw = "|".join(normalize_text(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def request(
    method: str,
    url: str,
    *,
    timeout: int = 25,
    retries: int = 3,
    backoff: float = 1.2,
    session: requests.Session | None = None,
    **kwargs: Any,
) -> requests.Response:
    client = session or requests
    headers = {
        "User-Agent": "StockLab-Free-AI/14.0 (+https://github.com/flyree140/stocklab)",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
        **kwargs.pop("headers", {}),
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.request(method, url, timeout=timeout, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(backoff * (2**attempt))
    raise RuntimeError(f"Request failed after {retries} attempts: {url}: {last_error}")


def request_json(url: str, **kwargs: Any) -> Any:
    return request("GET", url, **kwargs).json()


def request_text(url: str, **kwargs: Any) -> str:
    response = request("GET", url, **kwargs)
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def load_stocks() -> list[dict[str, Any]]:
    config = read_json(ROOT / "config" / "stocks.json", {}) or {}
    return list(config.get("stocks", []))


def load_settings() -> dict[str, Any]:
    return read_json(ROOT / "config" / "settings.json", {}) or {}


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TAIPEI)
    return dt.astimezone(TAIPEI)


def date_not_after(value: str | None, cutoff: date) -> bool:
    dt = parse_iso_datetime(value)
    return True if dt is None else dt.date() <= cutoff


def median(values: Iterable[float]) -> float:
    rows = sorted(float(value) for value in values)
    if not rows:
        return 0.0
    mid = len(rows) // 2
    return rows[mid] if len(rows) % 2 else (rows[mid - 1] + rows[mid]) / 2
