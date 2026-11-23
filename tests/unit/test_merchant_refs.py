"""Deterministic cross-merchant screen. Pure function: no database, no models."""

from __future__ import annotations

import pytest

from app.orchestration.merchant_refs import foreign_merchant_refs


@pytest.mark.parametrize(
    "message",
    [
        "Show decline rate for merchant_002 for October",
        "Show decline rate for MERCHANT_002",
        "merchant-2 volume please",
        "compare merchant 2 with ours",
        "merchant_0002 settlements",
    ],
)
def test_other_merchant_numbers_are_detected(message: str) -> None:
    assert foreign_merchant_refs(message, "merchant_001") == ["2"]


@pytest.mark.parametrize(
    "message",
    [
        "What was our volume in March?",
        "Show decline rate for merchant_001 for October",
        "merchant 1 volume",  # the caller's own merchant, written differently
        "Merchant analytics for March",  # no number: not a merchant reference
        "Show card type performance for March",
    ],
)
def test_own_or_absent_merchant_references_are_not_flagged(message: str) -> None:
    assert foreign_merchant_refs(message, "merchant_001") == []


def test_each_foreign_number_is_reported_once() -> None:
    message = "merchant_002 versus merchant_003 and merchant_002 again"
    assert foreign_merchant_refs(message, "merchant_001") == ["2", "3"]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Show the decline rate for merchant two.", ["2"]),
        ("merchant TWO volume", ["2"]),
        ("compare merchant ten with us", ["10"]),
        ("merchant_two settlements", ["2"]),
    ],
)
def test_merchant_numbers_written_as_words_are_detected(message: str, expected: list[str]) -> None:
    assert foreign_merchant_refs(message, "merchant_001") == expected


def test_word_number_for_the_callers_own_merchant_is_not_flagged() -> None:
    assert foreign_merchant_refs("merchant one volume", "merchant_001") == []


def test_the_callers_own_word_number_is_not_flagged_for_another_caller() -> None:
    assert foreign_merchant_refs("merchant two volume", "merchant_002") == []


@pytest.mark.parametrize(
    "message",
    [
        "What is the decline rate of the other merchant?",
        "Show volume for another merchant",
        "decline rate for a different merchant",
    ],
)
def test_indirect_other_merchant_references_are_flagged(message: str) -> None:
    assert foreign_merchant_refs(message, "merchant_001") == ["other"]
