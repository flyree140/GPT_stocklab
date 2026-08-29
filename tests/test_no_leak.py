from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import ROOT, read_json
from validate_no_leak import validate_snapshot


def test_demo_snapshot_has_no_future_answers():
    payload = read_json(ROOT / "data" / "snapshots" / "2025-08-15.json", {})
    assert validate_snapshot(payload) == []


def test_future_field_is_rejected():
    payload = {"as_of": "2025-08-15", "actual_return": 1.2, "audit": {"future_fields_present": False}}
    errors = validate_snapshot(payload)
    assert any("forbidden" in error for error in errors)
