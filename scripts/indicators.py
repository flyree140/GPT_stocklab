"""Dependency-light technical indicators used by both daily analysis and backtests."""
from __future__ import annotations

from typing import Any

from common import clamp, parse_number


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    result: list[float] = []
    for row in rows:
        value = parse_number(row.get(key))
        if value is not None:
            result.append(value)
    return result


def sma(values: list[float], period: int) -> float | None:
    return sum(values[-period:]) / period if len(values) >= period else None


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    series = [values[0]]
    for value in values[1:]:
        series.append(alpha * value + (1 - alpha) * series[-1])
    return series


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(delta, 0) for delta in deltas]
    losses = [max(-delta, 0) for delta in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def atr(rows: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(rows) <= period:
        return None
    true_ranges: list[float] = []
    previous_close: float | None = None
    for row in rows:
        high = parse_number(row.get("high"), parse_number(row.get("close")))
        low = parse_number(row.get("low"), parse_number(row.get("close")))
        close = parse_number(row.get("close"))
        if high is None or low is None or close is None:
            continue
        tr = high - low if previous_close is None else max(high - low, abs(high - previous_close), abs(low - previous_close))
        true_ranges.append(tr)
        previous_close = close
    return sma(true_ranges, period)


def stochastic(rows: list[dict[str, Any]], period: int = 9) -> tuple[float | None, float | None]:
    if len(rows) < period:
        return None, None
    k_values: list[float] = []
    k_prev = 50.0
    d_prev = 50.0
    for index in range(period - 1, len(rows)):
        window = rows[index - period + 1 : index + 1]
        highs = [parse_number(row.get("high"), parse_number(row.get("close"))) for row in window]
        lows = [parse_number(row.get("low"), parse_number(row.get("close"))) for row in window]
        close = parse_number(rows[index].get("close"))
        valid_highs = [value for value in highs if value is not None]
        valid_lows = [value for value in lows if value is not None]
        if not valid_highs or not valid_lows or close is None:
            continue
        highest = max(valid_highs)
        lowest = min(valid_lows)
        rsv = 50.0 if highest == lowest else (close - lowest) / (highest - lowest) * 100
        k_prev = k_prev * 2 / 3 + rsv / 3
        d_prev = d_prev * 2 / 3 + k_prev / 3
        k_values.append(k_prev)
    return (k_prev, d_prev) if k_values else (None, None)


def calculate(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    closes = _values(rows, "close")
    volumes = _values(rows, "volume")
    if not closes:
        return {
            "ma5": None,
            "ma20": None,
            "ma60": None,
            "ema12": None,
            "ema26": None,
            "rsi14": None,
            "macd": None,
            "macd_signal": None,
            "macd_hist": None,
            "k": None,
            "d": None,
            "atr": None,
            "atr_pct": None,
            "volume_ratio": None,
            "ibs": None,
            "support_20": None,
            "resistance_20": None,
        }
    ema12_series = ema_series(closes, 12)
    ema26_series = ema_series(closes, 26)
    macd_series = [a - b for a, b in zip(ema12_series[-len(ema26_series) :], ema26_series)]
    signal_series = ema_series(macd_series, 9)
    atr_value = atr(rows)
    k_value, d_value = stochastic(rows)
    latest = rows[-1]
    high = parse_number(latest.get("high"), closes[-1]) or closes[-1]
    low = parse_number(latest.get("low"), closes[-1]) or closes[-1]
    ibs_value = 0.5 if high == low else clamp((closes[-1] - low) / (high - low), 0, 1)
    volume_average = sma(volumes, 5)
    return {
        "ma5": round(sma(closes, 5), 4) if sma(closes, 5) is not None else None,
        "ma20": round(sma(closes, 20), 4) if sma(closes, 20) is not None else None,
        "ma60": round(sma(closes, 60), 4) if sma(closes, 60) is not None else None,
        "ema12": round(ema12_series[-1], 4) if ema12_series else None,
        "ema26": round(ema26_series[-1], 4) if ema26_series else None,
        "rsi14": round(rsi(closes, 14), 3) if rsi(closes, 14) is not None else None,
        "macd": round(macd_series[-1], 4) if macd_series else None,
        "macd_signal": round(signal_series[-1], 4) if signal_series else None,
        "macd_hist": round(macd_series[-1] - signal_series[-1], 4) if macd_series and signal_series else None,
        "k": round(k_value, 3) if k_value is not None else None,
        "d": round(d_value, 3) if d_value is not None else None,
        "atr": round(atr_value, 4) if atr_value is not None else None,
        "atr_pct": round(atr_value / closes[-1] * 100, 3) if atr_value is not None and closes[-1] else None,
        "volume_ratio": round(volumes[-1] / volume_average, 3) if volumes and volume_average else None,
        "ibs": round(ibs_value, 4),
        "support_20": round(min(closes[-20:]), 4),
        "resistance_20": round(max(closes[-20:]), 4),
    }
