"""Tests the pure retrieval metrics over heading paths (no database)."""

import pytest

from ruleslawyer.eval.metrics import is_grounded_by, recall_at_k, reciprocal_rank


def test_exact_path_is_grounded() -> None:
    """checks a chunk sitting on the grounding section itself counts."""
    assert is_grounded_by("Cover", "Cover")


def test_nested_path_is_grounded() -> None:
    """checks a chunk below the grounding section counts."""
    assert is_grounded_by("Cover > Half Cover", "Cover")


def test_partial_segment_is_not_grounded() -> None:
    """checks a path that only shares characters, not segments, is rejected."""
    assert not is_grounded_by("Covenants > Whatever", "Cover")


def test_unrelated_path_is_not_grounded() -> None:
    """checks an unrelated section is rejected."""
    assert not is_grounded_by("Resting > Long Rest", "Cover")


def test_recall_all_grounding_found() -> None:
    """checks recall is 1.0 when every grounding section appears in the top k."""
    retrieved = ["Cover > Half Cover", "Resting > Long Rest"]
    assert recall_at_k(retrieved, ["Cover", "Resting"], k=2) == 1.0


def test_recall_is_fractional() -> None:
    """checks recall is the fraction found, not a hit/miss."""
    retrieved = ["Cover > Half Cover", "Spellcasting"]
    assert recall_at_k(retrieved, ["Cover", "Resting"], k=2) == 0.5


def test_recall_ignores_paths_below_k() -> None:
    """checks a grounded path ranked past k does not count."""
    retrieved = ["Spellcasting", "Cover > Half Cover"]
    assert recall_at_k(retrieved, ["Cover"], k=1) == 0.0


def test_recall_empty_grounding_raises() -> None:
    """checks an unanswerable question is rejected rather than scored 0."""
    with pytest.raises(ValueError):
        recall_at_k(["Cover"], [], k=1)


def test_reciprocal_rank_top_result() -> None:
    """checks a grounded first result scores 1.0."""
    assert reciprocal_rank(["Cover > Half Cover", "Spellcasting"], ["Cover"]) == 1.0


def test_reciprocal_rank_second_result() -> None:
    """checks the first hit at rank 2 scores 0.5."""
    assert reciprocal_rank(["Spellcasting", "Cover > Half Cover"], ["Cover"]) == 0.5


def test_reciprocal_rank_no_hit() -> None:
    """checks no grounded result anywhere scores 0.0."""
    assert reciprocal_rank(["Spellcasting", "Resting > Long Rest"], ["Cover"]) == 0.0


def test_reciprocal_rank_empty_grounding_raises() -> None:
    """checks an unanswerable question is rejected rather than scored 0."""
    with pytest.raises(ValueError):
        reciprocal_rank(["Cover"], [])
