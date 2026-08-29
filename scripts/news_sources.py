"""Free point-in-time news adapters for StockLab.

Sources:
- Google News RSS for recent coverage.
- GDELT DOC 2.1 for recent and historical search.
- TWSE material-information rows supplied by market_sources.py.

Every row carries published_at and available_at, so historical validation can reject
items that were not known at the requested cutoff.
"""
from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus, urlparse

from common import TAIPEI, clamp, date_not_after, fingerprint, iso_now, normalize_text, parse_iso_datetime, request_json, request_text

LOGGER = logging.getLogger("stocklab.news")

SOURCE_QUALITY = {
    "mops.twse.com.tw": 0.98,
    "twse.com.tw": 0.97,
    "cna.com.tw": 0.91,
    "reuters.com": 0.93,
    "bloomberg.com": 0.91,
    "nikkei.com": 0.89,
    "ft.com": 0.89,
    "wsj.com": 0.89,
    "moneydj.com": 0.82,
    "anue.com": 0.80,
    "udn.com": 0.78,
    "ltn.com.tw": 0.76,
    "chinatimes.com": 0.74,
    "ettoday.net": 0.72,
    "yahoo.com": 0.70,
    "google.com": 0.65,
}


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def source_quality(url: str, source: str = "", official: bool = False) -> float:
    if official:
        return 0.98
    domain = _domain(url)
    for known, score in SOURCE_QUALITY.items():
        if domain == known or domain.endswith(f".{known}"):
            return score
    source_text = normalize_text(source)
    if any(word in source_text for word in ("中央社", "reuters", "路透", "bloomberg", "彭博")):
        return 0.88
    return 0.64


def relevance_score(stock: dict[str, Any], title: str, description: str = "") -> float:
    haystack = normalize_text(f"{title} {description}")
    if not haystack:
        return 0.0
    symbol = normalize_text(str(stock.get("symbol", "")))
    name = normalize_text(str(stock.get("name", "")))
    aliases = [normalize_text(str(item)) for item in stock.get("aliases", [])]
    scores: list[float] = []
    if symbol and re.search(rf"(?<!\d){re.escape(symbol)}(?!\d)", haystack):
        scores.append(1.0)
    if name and name in haystack:
        scores.append(0.98)
    for alias in aliases:
        if len(alias) >= 2 and alias in haystack:
            scores.append(0.92 if alias != name else 0.98)
    if not scores:
        industry = normalize_text(str(stock.get("industry", "")))
        return 0.25 if industry and industry in haystack else 0.0
    return clamp(max(scores) + min(0.05, 0.015 * (len(scores) - 1)), 0.0, 1.0)


def _parse_rss_datetime(value: str) -> datetime | None:
    parsed = parse_iso_datetime(value)
    if parsed:
        return parsed
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TAIPEI)
        return dt.astimezone(TAIPEI)
    except Exception:
        return None


def fetch_google_news(stock: dict[str, Any], as_of: date, lookback_days: int, max_items: int = 30) -> list[dict[str, Any]]:
    # Google News RSS is intended for recent news. GDELT handles older cutoffs.
    if (datetime.now(tz=TAIPEI).date() - as_of).days > 45:
        return []
    query = str(stock.get("news_query") or stock.get("name") or stock.get("symbol"))
    query = f"({query}) when:{max(1, int(lookback_days))}d"
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    try:
        xml = request_text(url, timeout=30)
        root = ET.fromstring(xml)
        entries = root.findall(".//item")
    except Exception as exc:
        LOGGER.warning("Google News RSS failed for %s: %s", stock.get("symbol"), exc)
        return []
    cutoff_start = as_of - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    for entry in entries[:max_items]:
        dt = _parse_rss_datetime(entry.findtext("pubDate") or entry.findtext("updated") or "")
        if dt and not (cutoff_start <= dt.date() <= as_of):
            continue
        title = _clean_html(entry.findtext("title") or "")
        description = _clean_html(entry.findtext("description") or "")
        url_value = str(entry.findtext("link") or "")
        source = _clean_html(entry.findtext("source") or "") or "Google News RSS"
        relevance = relevance_score(stock, title, description)
        if relevance < 0.35:
            continue
        published = (dt or datetime.combine(as_of, datetime.min.time(), tzinfo=TAIPEI)).isoformat()
        rows.append(
            {
                "id": fingerprint(str(stock.get("symbol")), title, url_value),
                "title": title,
                "description": description,
                "source": source,
                "url": url_value,
                "domain": _domain(url_value),
                "published_at": published,
                "available_at": published,
                "fetched_at": iso_now(),
                "source_quality": source_quality(url_value, source),
                "relevance": round(relevance, 3),
                "is_material_info": False,
                "provider": "google-news-rss",
            }
        )
    return rows


def _gdelt_datetime(value: str, fallback: date) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=TAIPEI)
            return dt.isoformat()
        except ValueError:
            continue
    parsed = parse_iso_datetime(text)
    return (parsed or datetime.combine(fallback, datetime.min.time(), tzinfo=TAIPEI)).isoformat()


def fetch_gdelt(stock: dict[str, Any], as_of: date, lookback_days: int, max_items: int = 40) -> list[dict[str, Any]]:
    query = str(stock.get("news_query") or stock.get("name") or stock.get("symbol"))
    start = datetime.combine(as_of - timedelta(days=lookback_days), datetime.min.time())
    end = datetime.combine(as_of, datetime.max.time().replace(microsecond=0))
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query={quote_plus(query)}&mode=artlist&maxrecords={min(max_items, 250)}"
        f"&format=json&sort=datedesc&startdatetime={start:%Y%m%d%H%M%S}&enddatetime={end:%Y%m%d%H%M%S}"
    )
    try:
        payload = request_json(url, timeout=45)
    except Exception as exc:
        LOGGER.warning("GDELT failed for %s: %s", stock.get("symbol"), exc)
        return []
    rows: list[dict[str, Any]] = []
    for article in payload.get("articles", []) if isinstance(payload, dict) else []:
        title = _clean_html(str(article.get("title", "")))
        description = _clean_html(str(article.get("snippet", "")))
        url_value = str(article.get("url", ""))
        relevance = relevance_score(stock, title, description)
        if relevance < 0.35:
            continue
        published = _gdelt_datetime(str(article.get("seendate", "")), as_of)
        if not date_not_after(published, as_of):
            continue
        source = str(article.get("domain") or _domain(url_value) or "GDELT")
        rows.append(
            {
                "id": fingerprint(str(stock.get("symbol")), title, url_value),
                "title": title,
                "description": description,
                "source": source,
                "url": url_value,
                "domain": _domain(url_value),
                "published_at": published,
                "available_at": published,
                "fetched_at": iso_now(),
                "source_quality": source_quality(url_value, source),
                "relevance": round(relevance, 3),
                "is_material_info": False,
                "provider": "gdelt-doc-2.1",
            }
        )
    return rows


def material_news(stock: dict[str, Any], rows: list[dict[str, Any]], as_of: date, lookback_days: int) -> list[dict[str, Any]]:
    symbol = str(stock.get("symbol", ""))
    start = as_of - timedelta(days=lookback_days)
    result: list[dict[str, Any]] = []
    for item in rows:
        if str(item.get("symbol", "")) != symbol:
            continue
        published = str(item.get("published_at") or item.get("available_at") or "")
        dt = parse_iso_datetime(published)
        if dt and not (start <= dt.date() <= as_of):
            continue
        title = _clean_html(str(item.get("title", "")))
        description = _clean_html(str(item.get("description", "")))
        result.append(
            {
                "id": fingerprint(symbol, title, published),
                "title": title,
                "description": description,
                "source": str(item.get("source") or "TWSE 每日重大訊息"),
                "url": str(item.get("url") or "https://mops.twse.com.tw/"),
                "domain": "mops.twse.com.tw",
                "published_at": published,
                "available_at": str(item.get("available_at") or published),
                "fetched_at": iso_now(),
                "source_quality": 0.98,
                "relevance": 1.0,
                "is_material_info": True,
                "provider": "twse-material-information",
            }
        )
    return result


def _dedupe(rows: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    # Normalize titles because the same event is often syndicated with different tracking URLs.
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_titles: list[str] = []
    for item in sorted(rows, key=lambda row: str(row.get("published_at", "")), reverse=True):
        item_id = str(item.get("id") or fingerprint(str(item.get("title", "")), str(item.get("url", ""))))
        normalized_title = normalize_text(str(item.get("title", "")))
        if item_id in seen_ids or not normalized_title:
            continue
        # Simple near-duplicate test: contained normalized titles longer than 14 chars.
        duplicate = any(
            len(normalized_title) >= 14
            and len(previous) >= 14
            and (normalized_title in previous or previous in normalized_title)
            for previous in seen_titles
        )
        if duplicate:
            continue
        seen_ids.add(item_id)
        seen_titles.append(normalized_title)
        selected.append(item)
        if len(selected) >= max_items:
            break
    return selected


def fetch_news_for_stock(
    stock: dict[str, Any],
    as_of: date,
    lookback_days: int,
    material_rows: list[dict[str, Any]] | None = None,
    max_items: int = 12,
) -> list[dict[str, Any]]:
    material_rows = material_rows or []
    rows = material_news(stock, material_rows, as_of, lookback_days)
    rows.extend(fetch_google_news(stock, as_of, lookback_days, max_items=max_items * 2))
    rows.extend(fetch_gdelt(stock, as_of, lookback_days, max_items=max_items * 3))
    rows = [item for item in rows if date_not_after(str(item.get("available_at", "")), as_of)]
    return _dedupe(rows, max_items=max_items)
