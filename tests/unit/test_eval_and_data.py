"""Evaluation metrics (pure functions) and the data generator's reproducibility and safety."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pytest

from app.jev.decisions import ScopeLabel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_dummy_data as gen  # noqa: E402
import run_jev_eval as ev  # noqa: E402

SUP = ScopeLabel.SUPPORTED_ANALYTICS.value
UNSAFE = ScopeLabel.PROMPT_INJECTION_OR_POLICY_BYPASS.value


def _p(**kw: object) -> ev.Prediction:
    base: dict[str, object] = {
        "case_id": "x",
        "expected_scope": SUP,
        "expected_tool": "get_transaction_volume",
        "expected_risk_flag": False,
        "category": "c",
        "predicted_scope": SUP,
        "scope_confidence": 0.95,
        "risk_probability": 0.01,
        "predicted_tool": "get_transaction_volume",
        "tool_confidence": 0.9,
    }
    base.update(kw)
    return ev.Prediction(**base)  # type: ignore[arg-type]


T = ev.Thresholds(scope=0.75, tool=0.75, risk=0.5)


def test_would_execute_requires_every_gate() -> None:
    assert ev.would_execute(_p(), T)
    assert not ev.would_execute(_p(risk_probability=0.9), T)
    assert not ev.would_execute(_p(predicted_scope="OUT_OF_SCOPE"), T)
    assert not ev.would_execute(_p(scope_confidence=0.5), T)
    assert not ev.would_execute(_p(predicted_tool="NO_TOOL"), T)
    assert not ev.would_execute(_p(tool_confidence=0.2), T)
    assert not ev.would_execute(_p(error="JevUnavailableError"), T)


def test_false_allow_counts_unsafe_cases_that_would_execute() -> None:
    preds = [
        _p(expected_scope=UNSAFE, predicted_scope=SUP),  # would execute -> false allow
        _p(expected_scope=UNSAFE, predicted_scope=UNSAFE, risk_probability=0.9),  # blocked -> fine
        _p(),  # supported, executes -> correct
    ]
    metrics = ev.compute_metrics(preds, T)
    assert metrics["false_allow_count"] == 1
    assert metrics["false_allow_rate"] == 0.5


def test_false_block_counts_supported_cases_not_executed() -> None:
    preds = [_p(), _p(scope_confidence=0.3), _p(predicted_tool="NO_TOOL")]
    metrics = ev.compute_metrics(preds, T)
    assert metrics["false_block_count"] == 2
    assert metrics["false_block_rate"] == pytest.approx(0.6667, abs=1e-4)


def test_tool_accuracy_and_wrong_tool_executions() -> None:
    preds = [
        _p(),
        _p(predicted_tool="get_decline_rate"),  # wrong tool, and it would execute
    ]
    metrics = ev.compute_metrics(preds, T)
    assert metrics["tool_selection_accuracy"] == 0.5
    assert metrics["wrong_tool_executions"] == 1


def test_per_label_precision_and_recall() -> None:
    preds = [
        _p(expected_scope=UNSAFE, predicted_scope=UNSAFE),
        _p(expected_scope=UNSAFE, predicted_scope=SUP),
        _p(expected_scope=SUP, predicted_scope=UNSAFE),
    ]
    row = ev.compute_metrics(preds, T)["per_label"][UNSAFE]
    assert row["precision"] == 0.5
    assert row["recall"] == 0.5


def test_errors_are_counted_and_not_treated_as_answers() -> None:
    preds = [
        _p(
            error="JevUnavailableError",
            predicted_scope=None,
            scope_confidence=None,
            risk_probability=None,
            predicted_tool=None,
            tool_confidence=None,
        )
    ]
    metrics = ev.compute_metrics(preds, T)
    assert metrics["errors"] == 1
    assert metrics["answered"] == 0
    assert metrics["scope_accuracy"] is None


def test_threshold_sweep_covers_grid_and_is_monotone_for_false_allow() -> None:
    preds = [
        _p(expected_scope=UNSAFE, predicted_scope=SUP, scope_confidence=c, tool_confidence=c)
        for c in (0.55, 0.7, 0.9)
    ]
    rows = ev.threshold_sweep(preds)
    assert [r["threshold"] for r in rows] == ev.THRESHOLD_GRID
    allows = [r["false_allow"] for r in rows]
    assert allows == sorted(allows, reverse=True)  # raising the threshold can only reduce allows


def test_dataset_loader_rejects_duplicates_and_unknown_labels(tmp_path: Path) -> None:
    good = {
        "id": "a",
        "category": "c",
        "input": "x",
        "expected_scope": SUP,
        "expected_tool": "t",
        "expected_risk_flag": False,
        "expected_policy_outcome": "ALLOW",
        "clarification_required": False,
        "role": "VIEWER",
    }
    dup = tmp_path / "dup.jsonl"
    dup.write_text(json.dumps(good) + "\n" + json.dumps(good) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        ev.load_cases(dup)
    bad_label = tmp_path / "bad.jsonl"
    bad_label.write_text(json.dumps({**good, "expected_scope": "MAYBE"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown expected_scope"):
        ev.load_cases(bad_label)


def test_shipped_dataset_is_valid_and_covers_required_categories() -> None:
    cases = ev.load_cases()
    categories = {c["category"] for c in cases}
    assert {
        "supported_analytics",
        "ambiguous",
        "unsupported_payment_action",
        "cross_merchant",
        "prompt_injection",
        "secret_extraction",
        "raw_credentials",
        "sql_or_unknown_tool",
    } <= categories
    assert len(cases) >= 60


def test_generator_output_matches_manifest() -> None:
    manifest = json.loads((ROOT / "data" / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == gen.SEED
    tables = gen.generate()
    for path, (fields, rows) in gen.output_files(tables).items():
        rel = path.relative_to(ROOT).as_posix()
        tmp = path.with_suffix(".unit.tmp")
        gen.write_csv(tmp, fields, rows)
        try:
            assert gen.sha256(tmp) == manifest["files"][rel], rel
        finally:
            tmp.unlink()


def test_generated_data_has_three_merchants_and_enough_volume() -> None:
    txns = list(gen.generate()["transactions"])
    assert len({t["merchant_id"] for t in txns}) == 3
    assert 5000 <= len(txns) <= 10000
    days = {t["transaction_timestamp"][:10] for t in txns}
    assert len(days) >= 90


def test_no_pan_cvv_pin_or_track_data_in_generated_csvs() -> None:
    forbidden_headers = {
        "pan",
        "card_number",
        "cvv",
        "cvc",
        "pin",
        "pin_block",
        "track_data",
        "track2",
        "expiry",
    }
    pan_like = re.compile(r"\b\d{13,19}\b")
    for csv_path in (ROOT / "data").glob("*.csv"):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = [h.lower() for h in next(reader)]
            assert forbidden_headers.isdisjoint(header), csv_path.name
            for row in reader:
                assert not any(pan_like.search(cell) for cell in row), csv_path.name
