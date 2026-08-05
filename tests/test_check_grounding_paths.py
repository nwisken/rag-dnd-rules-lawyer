"""Tests the pure prefix matching of the grounding path checker (no database)."""

from scripts.check_grounding_paths import is_grounded_by


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
