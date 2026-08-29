"""Transparent scoring and daily top-pick selection."""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from common import clamp, median, parse_iso_datetime, parse_number


def _recency_weight(item: dict[str, Any], as_of: date) -> float:
    dt = parse_iso_datetime(str(item.get("available_at") or item.get("published_at") or ""))
    age = max(0, (as_of - dt.date()).days) if dt else 0
    return math.exp(-age / 5.0)


def score_news(news: list[dict[str, Any]], as_of: date) -> tuple[float, dict[str, Any]]:
    if not news:
        return 0.0, {"weighted_items": 0, "positive": 0, "negative": 0, "average_relevance": 0.0}
    numerator = 0.0
    denominator = 0.0
    positive = 0
    negative = 0
    relevances: list[float] = []
    for item in news:
        impact = float(item.get("impact_score", 0) or 0)
        confidence = clamp(float(item.get("confidence", 0.5) or 0.5), 0.0, 1.0)
        relevance = clamp(float(item.get("relevance", 0.5) or 0.5), 0.0, 1.0)
        quality = clamp(float(item.get("source_quality", 0.6) or 0.6), 0.0, 1.0)
        recency = _recency_weight(item, as_of)
        weight = max(0.03, confidence * relevance * quality * recency)
        numerator += impact * weight
        denominator += weight
        relevances.append(relevance)
        if impact > 15:
            positive += 1
        if impact < -15:
            negative += 1
    raw = numerator / denominator if denominator else 0.0
    evidence_factor = min(1.0, 0.55 + math.log1p(len(news)) / 3.4)
    score = clamp(raw * evidence_factor, -100, 100)
    return round(score, 1), {
        "weighted_items": len(news),
        "positive": positive,
        "negative": negative,
        "average_relevance": round(sum(relevances) / len(relevances), 3),
    }


def score_technical(technical: dict[str, Any], price: dict[str, Any]) -> float:
    close = parse_number(price.get("close"))
    if close is None:
        return 50.0
    score = 50.0
    ma5 = parse_number(technical.get("ma5"))
    ma20 = parse_number(technical.get("ma20"))
    ma60 = parse_number(technical.get("ma60"))
    if ma5 is not None:
        score += 7 if close >= ma5 else -7
    if ma20 is not None:
        score += 9 if close >= ma20 else -9
    if ma60 is not None:
        score += 8 if close >= ma60 else -8
    if ma5 is not None and ma20 is not None:
        score += 7 if ma5 >= ma20 else -7
    macd_hist = parse_number(technical.get("macd_hist"))
    if macd_hist is not None:
        score += 7 if macd_hist > 0 else -7
    rsi = parse_number(technical.get("rsi14"))
    if rsi is not None:
        if 50 <= rsi <= 70:
            score += 8
        elif 35 <= rsi < 50:
            score += 1
        elif rsi > 78:
            score -= 9
        elif rsi < 28:
            score -= 4
    volume_ratio = parse_number(technical.get("volume_ratio"))
    change = parse_number(price.get("change_pct"), 0) or 0
    if volume_ratio is not None and volume_ratio >= 1.4:
        score += 5 if change >= 0 else -5
    return round(clamp(score, 0, 100), 1)


def score_fundamental(fundamental: dict[str, Any]) -> float:
    available = [fundamental.get(key) for key in ("revenue_yoy", "revenue_mom", "pe", "pb", "dividend_yield")]
    if not any(value is not None for value in available):
        return 50.0
    score = 50.0
    yoy = parse_number(fundamental.get("revenue_yoy"))
    mom = parse_number(fundamental.get("revenue_mom"))
    pe = parse_number(fundamental.get("pe"))
    pb = parse_number(fundamental.get("pb"))
    yield_value = parse_number(fundamental.get("dividend_yield"))
    if yoy is not None:
        score += clamp(yoy / 2.2, -18, 20)
    if mom is not None:
        score += clamp(mom / 3.0, -8, 8)
    if pe is not None:
        if 0 < pe <= 18:
            score += 8
        elif pe <= 28:
            score += 3
        elif pe > 50:
            score -= 10
        elif pe <= 0:
            score -= 12
    if pb is not None and pb > 8:
        score -= 5
    if yield_value is not None:
        score += clamp((yield_value - 2.0) * 1.8, -3, 7)
    return round(clamp(score, 0, 100), 1)


def score_institutional(institutional: dict[str, Any], latest_volume: float | None = None) -> float:
    if not institutional or institutional.get("date") is None:
        return 50.0
    total = parse_number(institutional.get("total_net"), 0) or 0
    foreign = parse_number(institutional.get("foreign_net"), 0) or 0
    trust = parse_number(institutional.get("investment_trust_net"), 0) or 0
    denominator = max(abs(latest_volume or 0), 1_000_000)
    normalized = total / denominator
    score = 50 + clamp(normalized * 32, -24, 24)
    if foreign > 0 and trust > 0:
        score += 6
    elif foreign < 0 and trust < 0:
        score -= 6
    return round(clamp(score, 0, 100), 1)


def score_risk(technical: dict[str, Any], fundamental: dict[str, Any], news: list[dict[str, Any]]) -> float:
    risk = 22.0
    atr_pct = parse_number(technical.get("atr_pct"))
    if atr_pct is not None:
        risk += clamp((atr_pct - 1.5) * 8.5, -6, 24)
    rsi = parse_number(technical.get("rsi14"))
    if rsi is not None and rsi > 78:
        risk += 10
    pe = parse_number(fundamental.get("pe"))
    if pe is not None and pe > 45:
        risk += 10
    severe_negative = sum(1 for item in news if float(item.get("impact_score", 0) or 0) <= -40)
    risk += min(28, severe_negative * 9)
    low_quality = sum(1 for item in news if float(item.get("source_quality", 0.6) or 0.6) < 0.6)
    risk += min(8, low_quality * 1.5)
    return round(clamp(risk, 0, 100), 1)


def data_completeness(
    history: list[dict[str, Any]],
    technical: dict[str, Any],
    fundamental: dict[str, Any],
    institutional: dict[str, Any],
    news: list[dict[str, Any]],
) -> float:
    checks = {
        "price_history": min(1.0, len(history) / 60),
        "technical": sum(technical.get(key) is not None for key in ("ma20", "ma60", "rsi14", "macd", "atr")) / 5,
        "fundamental": sum(fundamental.get(key) is not None for key in ("revenue_yoy", "revenue_mom", "pe", "pb", "dividend_yield")) / 5,
        "institutional": 1.0 if institutional.get("date") else 0.0,
        "news": min(1.0, len(news) / 4),
    }
    weights = {"price_history": 0.24, "technical": 0.21, "fundamental": 0.22, "institutional": 0.14, "news": 0.19}
    return round(sum(checks[key] * weights[key] for key in checks) * 100, 1)


def composite_scores(
    *,
    news_score: float,
    technical_score: float,
    fundamental_score: float,
    institutional_score: float,
    risk_score: float,
    completeness: float,
    weights: dict[str, float] | None = None,
) -> float:
    weights = weights or {
        "news": 0.33,
        "technical": 0.24,
        "fundamental": 0.15,
        "institutional": 0.10,
        "completeness": 0.08,
        "risk_penalty": 0.18,
    }
    score = (
        50
        + news_score * float(weights.get("news", 0.33))
        + (technical_score - 50) * float(weights.get("technical", 0.24))
        + (fundamental_score - 50) * float(weights.get("fundamental", 0.15))
        + (institutional_score - 50) * float(weights.get("institutional", 0.10))
        + (completeness - 50) * float(weights.get("completeness", 0.08))
        - risk_score * float(weights.get("risk_penalty", 0.18))
    )
    return round(clamp(score, 0, 100), 1)


def recommendation(composite: float, news_score: float, risk: float, completeness: float) -> dict[str, Any]:
    if completeness < 45:
        return {
            "direction": "neutral",
            "label": "資料不足",
            "reason": "可用資料不足，總分已折扣；先補齊價格、新聞或官方資料再判讀。",
            "risks": ["資料缺口可能造成偏差", "不要以此分數直接交易"],
        }
    if composite >= 68 and risk <= 65:
        label, direction = "偏多研究", "positive"
    elif composite <= 38 or risk >= 78:
        label, direction = "風險偏高", "negative"
    else:
        label, direction = "中性觀察", "neutral"
    alignment = "一致" if (composite >= 55 and news_score >= 0) or (composite < 55 and news_score < 0) else "分歧"
    return {
        "direction": direction,
        "label": label,
        "reason": f"新聞與傳統面訊號目前呈現{alignment}；綜合分 {composite:.1f}、風險分 {risk:.1f}、資料完整度 {completeness:.1f}%。",
        "risks": ["新聞可能被市場提前反映", "開源模型可能誤判語意", "本工具不構成投資建議"],
    }


def select_top_picks(stocks: list[dict[str, Any]], settings: dict[str, Any]) -> list[str]:
    """Return only stocks that pass every transparent Top Pick gate.

    It is safer to show fewer than ``top_n`` picks than to silently promote an
    incomplete, high-risk, or low-relevance stock just to fill the row.
    """
    top_n = int(settings.get("daily_top_n", 5))
    min_composite = float(settings.get("minimum_top_pick_composite", 55))
    min_complete = float(settings.get("minimum_top_pick_completeness", 58))
    max_risk = float(settings.get("maximum_top_pick_risk", 72))
    min_relevance = float(settings.get("minimum_top_pick_news_relevance", 0.55))
    eligible = []
    for stock in stocks:
        scores = stock.get("scores", {})
        audit = stock.get("news_audit", {})
        if stock.get("stale"):
            continue
        if float(scores.get("composite", 0)) < min_composite:
            continue
        if float(scores.get("completeness", 0)) < min_complete:
            continue
        if float(scores.get("risk", 100)) > max_risk:
            continue
        if stock.get("news") and float(audit.get("average_relevance", 0)) < min_relevance:
            continue
        eligible.append(stock)
    eligible.sort(
        key=lambda item: (
            float(item.get("scores", {}).get("composite", 0)),
            float(item.get("scores", {}).get("news", 0)),
            float(item.get("scores", {}).get("completeness", 0)),
        ),
        reverse=True,
    )
    return [str(stock.get("symbol")) for stock in eligible[:top_n]]


def market_summary(stocks: list[dict[str, Any]]) -> dict[str, Any]:
    all_news = [item for stock in stocks for item in stock.get("news", [])]
    positive = sum(1 for item in all_news if float(item.get("impact_score", 0) or 0) > 15)
    negative = sum(1 for item in all_news if float(item.get("impact_score", 0) or 0) < -15)
    news_scores = [float(stock.get("scores", {}).get("news", 0)) for stock in stocks]
    temperature = round(clamp(50 + (sum(news_scores) / max(1, len(news_scores))) * 0.5, 0, 100), 1)
    label = "positive" if temperature >= 58 else "negative" if temperature <= 42 else "neutral"
    completeness_values = [float(stock.get("scores", {}).get("completeness", 0)) for stock in stocks]
    return {
        "news_temperature": temperature,
        "sentiment_label": label,
        "positive_news": positive,
        "negative_news": negative,
        "median_completeness": round(median(completeness_values), 1),
    }
