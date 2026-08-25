"""Tests the pure generation-eval helpers (no LLM, no database)."""

import pytest

from ruleslawyer.eval.judge import _strip_to_json, faithfulness_score, refusal_accuracy


def test_faithfulness_all_supported() -> None:
    """checks every claim supported scores 1.0."""
    claims = [{"claim": "a", "supported": True}, {"claim": "b", "supported": True}]
    assert faithfulness_score(claims) == 1.0


def test_faithfulness_is_fractional() -> None:
    """checks the score is supported / total, not a hit/miss."""
    claims = [{"claim": "a", "supported": True}, {"claim": "b", "supported": False}]
    assert faithfulness_score(claims) == 0.5


def test_faithfulness_none_supported() -> None:
    """checks no supported claims scores 0.0."""
    claims = [{"claim": "a", "supported": False}, {"claim": "b", "supported": False}]
    assert faithfulness_score(claims) == 0.0


def test_faithfulness_empty_raises() -> None:
    """checks a refusal (zero claims) is rejected rather than scored."""
    with pytest.raises(ValueError):
        faithfulness_score([])


def test_refusal_accuracy_all_refused() -> None:
    """checks every question correctly refused scores 1.0."""
    assert refusal_accuracy([True, True, True]) == 1.0


def test_refusal_accuracy_is_fractional() -> None:
    """checks the score is correct refusals / total."""
    assert refusal_accuracy([True, False, False, False]) == 0.25


def test_refusal_accuracy_empty_raises() -> None:
    """checks scoring with no unanswerable questions is rejected."""
    with pytest.raises(ValueError):
        refusal_accuracy([])


def test_strip_to_json_plain() -> None:
    """checks a clean JSON object is returned unchanged."""
    assert _strip_to_json('{"claims": []}') == '{"claims": []}'


def test_strip_to_json_code_fence() -> None:
    """checks a ```json fenced object has its fences stripped."""
    raw = '```json\n{"claims": []}\n```'
    assert _strip_to_json(raw) == '{"claims": []}'


def test_strip_to_json_surrounding_prose() -> None:
    """checks an object wrapped in prose is extracted."""
    raw = 'Here is the result: {"claims": []}. Done.'
    assert _strip_to_json(raw) == '{"claims": []}'
