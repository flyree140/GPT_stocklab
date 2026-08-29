from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scoring import composite_scores, score_news, select_top_picks


def test_positive_news_scores_positive():
    score, audit = score_news(
        [{
            "impact_score": 70,
            "confidence": 0.9,
            "relevance": 1.0,
            "source_quality": 0.9,
            "available_at": "2025-08-15T10:00:00+08:00",
        }],
        date(2025, 8, 15),
    )
    assert score > 0
    assert audit["positive"] == 1


def test_risk_penalty_lowers_composite():
    low = composite_scores(news_score=40, technical_score=70, fundamental_score=60, institutional_score=55, risk_score=20, completeness=90)
    high = composite_scores(news_score=40, technical_score=70, fundamental_score=60, institutional_score=55, risk_score=80, completeness=90)
    assert low > high


def test_top_pick_filters_high_risk():
    stocks = [
        {"symbol": "A", "scores": {"composite": 90, "risk": 90, "completeness": 90, "news": 80}, "news": [{}], "news_audit": {"average_relevance": 0.9}},
        {"symbol": "B", "scores": {"composite": 80, "risk": 20, "completeness": 90, "news": 60}, "news": [{}], "news_audit": {"average_relevance": 0.9}},
    ]
    settings = {"daily_top_n": 1, "minimum_top_pick_composite": 55, "minimum_top_pick_completeness": 58, "maximum_top_pick_risk": 72, "minimum_top_pick_news_relevance": 0.55}
    assert select_top_picks(stocks, settings) == ["B"]


def test_top_pick_does_not_fill_with_ineligible_stock():
    stocks = [
        {"symbol": "LOW", "scores": {"composite": 40, "risk": 20, "completeness": 90, "news": 10}, "news": [{}], "news_audit": {"average_relevance": 0.9}, "stale": False},
        {"symbol": "STALE", "scores": {"composite": 90, "risk": 20, "completeness": 90, "news": 80}, "news": [{}], "news_audit": {"average_relevance": 0.9}, "stale": True},
    ]
    settings = {"daily_top_n": 5, "minimum_top_pick_composite": 55, "minimum_top_pick_completeness": 58, "maximum_top_pick_risk": 72, "minimum_top_pick_news_relevance": 0.55}
    assert select_top_picks(stocks, settings) == []
