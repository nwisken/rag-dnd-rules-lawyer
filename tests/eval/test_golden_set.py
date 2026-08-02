"""Tests the golden set loader and its validation"""

import json
from pathlib import Path
from typing import Any

import pytest

from ruleslawyer.eval.golden_set import (
    GoldenQuestion,
    load_golden_set,
    to_question,
    validate_records,
)

GOLDEN_SET = Path(__file__).parents[2] / "evals" / "golden_set.jsonl"


# factory for creating valid records for testing
def make_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "sneak-attack-thrown-dagger",
        "question": "Does Sneak Attack work with a thrown dagger?",
        "edition": "srd51",
        "answerable": True,
        "grounding": ["Rogue > Class Features > Sneak Attack"],
        "expected_answer": "Yes, a dagger has the finesse property.",
        "difficulty": "medium",
    }
    return record | overrides


def test_valid_record_passes() -> None:
    """checks a well formed record produces no errors"""
    assert validate_records([make_record()]) == []


def test_refusal_record_passes() -> None:
    """checks answerable False with empty grounding is legal"""
    record = make_record(answerable=False, grounding=[])
    assert validate_records([record]) == []


def test_null_edition_passes() -> None:
    """checks an edition agnostic question is legal"""
    assert validate_records([make_record(edition=None)]) == []


def test_missing_field_reported_once() -> None:
    """checks a missing field is not also reported as an invalid value"""
    record = make_record()
    del record["difficulty"]
    errors = validate_records([record])
    assert len(errors) == 1
    assert "missing fields ['difficulty']" in errors[0]


def test_unknown_field_reported() -> None:
    """checks a typo'd key is caught rather than silently ignored"""
    errors = validate_records([make_record(dificulty="easy")])
    assert len(errors) == 1
    assert "unknown fields ['dificulty']" in errors[0]


def test_bad_edition_reported() -> None:
    """checks an edition outside the allowed set is caught"""
    errors = validate_records([make_record(edition="srd53")])
    assert len(errors) == 1
    assert "edition 'srd53'" in errors[0]


def test_bad_difficulty_reported() -> None:
    """checks a difficulty outside the allowed set is caught"""
    errors = validate_records([make_record(difficulty="trivial")])
    assert len(errors) == 1
    assert "difficulty 'trivial'" in errors[0]


def test_empty_grounding_path_reported() -> None:
    """checks an empty label is caught before it can free match every chunk"""
    errors = validate_records([make_record(grounding=["Combat", ""])])
    assert len(errors) == 1
    assert "grounding contains an empty string" in errors[0]


def test_answerable_without_grounding_reported() -> None:
    """checks a real question that forgot its grounding is caught"""
    errors = validate_records([make_record(grounding=[])])
    assert len(errors) == 1
    assert "answerable=True" in errors[0]


def test_refusal_with_grounding_reported() -> None:
    """checks a refusal question that kept its grounding is caught"""
    errors = validate_records([make_record(answerable=False)])
    assert len(errors) == 1
    assert "answerable=False" in errors[0]


def test_duplicate_id_reported() -> None:
    """checks uniqueness is judged across the file, not per record"""
    records = [make_record(), make_record(question="A different question?")]
    errors = validate_records(records)
    assert errors == ["id 'sneak-attack-thrown-dagger' used by 2 records"]


def test_every_problem_reported() -> None:
    """checks validation accumulates rather than stopping at the first problem"""
    records = [make_record(edition="srd53"), make_record(id="other", difficulty="trivial")]
    assert len(validate_records(records)) == 2


def test_to_question_converts_grounding_to_tuple() -> None:
    """checks the JSON list becomes a hashable tuple"""
    question = to_question(make_record())
    assert question.grounding == ("Rogue > Class Features > Sneak Attack",)
    assert hash(question)


def test_load_golden_set_raises_with_every_problem(tmp_path: Path) -> None:
    """checks a bad file raises once, listing all its problems"""
    path = tmp_path / "bad.jsonl"
    records = [make_record(edition="srd53"), make_record(id="other", difficulty="trivial")]
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_golden_set(path)

    assert "srd53" in str(excinfo.value)
    assert "trivial" in str(excinfo.value)


def test_real_golden_set_loads() -> None:
    """checks the committed golden set is valid and complete"""
    questions = load_golden_set(GOLDEN_SET)
    assert len(questions) == 25
    assert all(isinstance(q, GoldenQuestion) for q in questions)
    assert sum(not q.answerable for q in questions) == 5
