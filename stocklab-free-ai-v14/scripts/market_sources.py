"""Free market-data adapters.

Primary prices use Yahoo's public chart endpoint because it returns enough history in one
request. Official TWSE monthly data is the fallback. Fundamentals and material information
use TWSE OpenAPI. Institutional data uses the TWSE T86 report.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from common import TAIPEI, clamp, iso_now, parse_int, parse_number, request_json

LOGGER = logging.getLogger("stocklab.market")


def _pick(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    normalized = {str(key).replace(" ", "").lower(): value for key, value in row.items()}
    for name in names:
        key = name.replace(" ", "").lower()
        if key in normalized and normalized[key] not in (None, ""):
            return normalized[key]
    return None


def yahoo_ticker(symbol: str, market: str = "TWSE") -> str:
    if symbol.startswith("^") or "." in symbol:
        return symbol
    return f"{symbol}.TWO" if market.upper() in {"TPEX", "OTC"} else f"{symbol}.TW"


def fetch_yahoo_history(symbol: str, market: str, start: date, end: date) -> list[dict[str, Any]]:
    ticker = yahoo_ticker(symbol, market)
    start_epoch = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    end_epoch = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}"
        f"?period1={start_epoch}&period2={end_epoch}&interval=1d&events=history&includeAdjustedClose=true"
    )
    payload = request_json(url, timeout=30)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"Yahoo history unavailable for {ticker}: {error}")
    timestamps = result.get("timestamp") or []
    quote_data = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
    rows: list[dict[str, Any]] = []
    for index, stamp in enumerate(timestamps):
        close = (quote_data.get("close") or [None] * len(timestamps))[index]
        if close is None:
            continue
        dt = datetime.fromtimestamp(stamp, tz=timezone.utc).astimezone(TAIPEI)
        if not (start <= dt.date() <= end):
            continue
        rows.append(
            {
                "date": dt.date().isoformat(),
                "open": _list_value(quote_data.get("open"), index),
                "high": _list_value(quote_data.get("high"), index),
                "low": _list_value(quote_data.get("low"), index),
                "close": round(float(close), 4),
                "adj_close": _list_value(adjusted, index),
                "volume": parse_int(_list_value(quote_data.get("volume"), index), 0),
                "source": "Yahoo Finance chart (free fallback)",
                "available_at": dt.date().isoformat(),
            }
        )
    return rows


def _list_value(values: list[Any] | None, index: int) -> Any:
    if not values or index >= len(values):
        return None
    value = values[index]
    return round(float(value), 4) if isinstance(value, (int, float)) else value


def _parse_roc_date(value: str) -> str | None:
    try:
        year_text, month_text, day_text = value.strip().split("/")
        return date(int(year_text) + 1911, int(month_text), int(day_text)).isoformat()
    except Exception:
        return None


def fetch_twse_month(symbol: str, year: int, month: int) -> list[dict[str, Any]]:
    url = (
        "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
        f"?date={year:04d}{month:02d}01&stockNo={quote(symbol)}&response=json"
    )
    payload = request_json(url, timeout=30)
    fields = payload.get("fields") or []
    data = payload.get("data") or []
    if payload.get("stat") not in {"OK", None} and not data:
        return []
    rows = []
    for values in data:
        row = dict(zip(fields, values))
        day = _parse_roc_date(str(_pick(row, "日期") or ""))
        close = parse_number(_pick(row, "收盤價"))
        if not day or close is None:
            continue
        rows.append(
            {
                "date": day,
                "open": parse_number(_pick(row, "開盤價")),
                "high": parse_number(_pick(row, "最高價")),
                "low": parse_number(_pick(row, "最低價")),
                "close": close,
                "adj_close": close,
                "volume": parse_int(_pick(row, "成交股數"), 0),
                "source": "TWSE STOCK_DAY",
                "available_at": day,
            }
        )
    return rows


def fetch_twse_history(symbol: str, start: date, end: date) -> list[dict[str, Any]]:
    current = date(start.year, start.month, 1)
    rows: list[dict[str, Any]] = []
    while current <= end:
        rows.extend(fetch_twse_month(symbol, current.year, current.month))
        next_month = current.month % 12 + 1
        next_year = current.year + (1 if current.month == 12 else 0)
        current = date(next_year, next_month, 1)
        time.sleep(0.35)
    by_date = {row["date"]: row for row in rows if start.isoformat() <= row["date"] <= end.isoformat()}
    return [by_date[key] for key in sorted(by_date)]


def fetch_price_history(stock: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    symbol = str(stock["symbol"])
    market = str(stock.get("market", "TWSE"))
    try:
        rows = fetch_yahoo_history(symbol, market, start, end)
        if len(rows) >= 20:
            return rows
    except Exception as exc:
        LOGGER.warning("Yahoo price failed for %s: %s", symbol, exc)
    if market.upper() == "TWSE":
        try:
            return fetch_twse_history(symbol, start, end)
        except Exception as exc:
            LOGGER.warning("TWSE price failed for %s: %s", symbol, exc)
    return []


def fetch_valuation_map() -> dict[str, dict[str, Any]]:
    url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    try:
        payload = request_json(url, timeout=30)
    except Exception as exc:
        LOGGER.warning("Valuation endpoint failed: %s", exc)
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in payload if isinstance(payload, list) else []:
        symbol = str(_pick(row, "證券代號", "Code", "股票代號") or "").strip()
        if not symbol:
            continue
        result[symbol] = {
            "pe": parse_number(_pick(row, "本益比", "PEratio")),
            "pb": parse_number(_pick(row, "股價淨值比", "PBratio")),
            "dividend_yield": parse_number(_pick(row, "殖利率(%)", "殖利率", "DividendYield")),
            "source": "TWSE BWIBBU_ALL",
            "fetched_at": iso_now(),
        }
    return result


def fetch_revenue_map() -> dict[str, dict[str, Any]]:
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
    try:
        payload = request_json(url, timeout=35)
    except Exception as exc:
        LOGGER.warning("Revenue endpoint failed: %s", exc)
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in payload if isinstance(payload, list) else []:
        symbol = str(_pick(row, "公司代號", "公司代碼") or "").strip()
        if not symbol:
            continue
        period = str(_pick(row, "資料年月", "出表日期") or "")
        result[symbol] = {
            "period": period,
            "revenue": parse_int(_pick(row, "營業收入-當月營收", "當月營收")),
            "revenue_mom": parse_number(_pick(row, "營業收入-上月比較增減(%)", "上月比較增減(%)")),
            "revenue_yoy": parse_number(_pick(row, "營業收入-去年同月增減(%)", "去年同月增減(%)")),
            "source": "TWSE t187ap05_L",
            "fetched_at": iso_now(),
        }
    return result


def fetch_material_information() -> list[dict[str, Any]]:
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
    try:
        payload = request_json(url, timeout=35)
    except Exception as exc:
        LOGGER.warning("Material information endpoint failed: %s", exc)
        return []
    rows = []
    for row in payload if isinstance(payload, list) else []:
        symbol = str(_pick(row, "公司代號") or "").strip()
        title = str(_pick(row, "主旨") or "").strip()
        detail = str(_pick(row, "說明") or "").strip()
        report_date = str(_pick(row, "發言日期", "出表日期") or "").strip()
        report_time = str(_pick(row, "發言時間") or "").strip()
        available = _mops_datetime(report_date, report_time)
        if not symbol or not title:
            continue
        rows.append(
            {
                "symbol": symbol,
                "company": str(_pick(row, "公司名稱") or ""),
                "title": title,
                "description": detail,
                "published_at": available,
                "available_at": available,
                "source": "TWSE 每日重大訊息",
                "url": "https://mops.twse.com.tw/",
                "is_material_info": True,
                "raw": row,
            }
        )
    return rows


def _mops_datetime(date_text: str, time_text: str) -> str:
    digits = "".join(char for char in date_text if char.isdigit())
    time_digits = "".join(char for char in time_text if char.isdigit()).ljust(6, "0")[:6]
    try:
        if len(digits) == 7:  # ROC yyyMMdd
            year = int(digits[:3]) + 1911
            month = int(digits[3:5])
            day = int(digits[5:7])
        elif len(digits) == 8:
            year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        else:
            raise ValueError
        hour, minute, second = int(time_digits[:2]), int(time_digits[2:4]), int(time_digits[4:6])
        return datetime(year, month, day, hour, minute, second, tzinfo=TAIPEI).isoformat()
    except Exception:
        return iso_now()


def fetch_institutional_map(as_of: date) -> tuple[str | None, dict[str, dict[str, Any]]]:
    for offset in range(0, 12):
        day = as_of - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        url = (
            "https://www.twse.com.tw/rwd/zh/fund/T86"
            f"?date={day:%Y%m%d}&selectType=ALLBUT0999&response=json"
        )
        try:
            payload = request_json(url, timeout=35)
        except Exception as exc:
            LOGGER.debug("T86 %s failed: %s", day, exc)
            continue
        fields = payload.get("fields") or []
        data = payload.get("data") or []
        if not data:
            continue
        result: dict[str, dict[str, Any]] = {}
        for values in data:
            row = dict(zip(fields, values))
            symbol = str(_pick(row, "證券代號") or "").strip()
            if not symbol:
                continue
            foreign = parse_int(_pick(row, "外陸資買賣超股數(不含外資自營商)", "外資及陸資買賣超股數(不含外資自營商)", "外資及陸資買賣超股數"), 0) or 0
            trust = parse_int(_pick(row, "投信買賣超股數"), 0) or 0
            dealer = parse_int(_pick(row, "自營商買賣超股數", "自營商買賣超股數(自行買賣)", "自營商買賣超股數(避險)"), 0) or 0
            total = parse_int(_pick(row, "三大法人買賣超股數"), foreign + trust + dealer)
            result[symbol] = {
                "date": day.isoformat(),
                "foreign_net": foreign,
                "investment_trust_net": trust,
                "dealer_net": dealer,
                "total_net": total,
                "source": "TWSE T86",
                "available_at": datetime(day.year, day.month, day.day, 15, 30, tzinfo=TAIPEI).isoformat(),
                "fetched_at": iso_now(),
            }
        return day.isoformat(), result
    return None, {}


def fetch_taiex_snapshot() -> dict[str, Any] | None:
    url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX"
    try:
        payload = request_json(url, timeout=30)
    except Exception as exc:
        LOGGER.warning("TAIEX endpoint failed: %s", exc)
        return None
    for row in payload if isinstance(payload, list) else []:
        name = str(_pick(row, "指數") or "")
        if "發行量加權" in name:
            sign = -1 if str(_pick(row, "漲跌") or "") in {"-", "－"} else 1
            return {
                "name": name,
                "close": parse_number(_pick(row, "收盤指數")),
                "change": sign * (parse_number(_pick(row, "漲跌點數"), 0) or 0),
                "change_pct": sign * (parse_number(_pick(row, "漲跌百分比"), 0) or 0),
                "source": "TWSE MI_INDEX",
                "fetched_at": iso_now(),
            }
    return None
