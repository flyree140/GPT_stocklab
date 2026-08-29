from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from indicators import calculate


def test_indicators_have_expected_fields():
    rows = []
    for index in range(1, 90):
        rows.append({"date": f"2025-01-{min(index, 28):02d}", "open": index, "high": index + 1, "low": index - 1, "close": index, "volume": 1000 + index})
    result = calculate(rows)
    assert result["ma5"] is not None
    assert result["ma20"] is not None
    assert result["ma60"] is not None
    assert 0 <= result["rsi14"] <= 100
    assert result["atr"] is not None
