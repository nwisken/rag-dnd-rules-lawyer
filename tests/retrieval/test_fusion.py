"""Tests for reciprocal_rank_fusion."""

from ruleslawyer.retrieval.fusion import reciprocal_rank_fusion


def test_identical_lists_preserve_order() -> None:
    paths = ["A", "B", "C"]
    result = reciprocal_rank_fusion(paths, paths)
    assert result == ["A", "B", "C"]


def test_disjoint_lists_interleave_by_rank() -> None:
    vector = ["A", "B"]
    text = ["C", "D"]
    result = reciprocal_rank_fusion(vector, text)
    # A and C tie at rank 1 in their respective lists, B and D tie at rank 2;
    # sorted() is stable so input order breaks ties: A before C, B before D
    assert result == ["A", "C", "B", "D"]


def test_empty_list_returns_other() -> None:
    paths = ["A", "B", "C"]
    assert reciprocal_rank_fusion(paths, []) == ["A", "B", "C"]
    assert reciprocal_rank_fusion([], paths) == ["A", "B", "C"]


def test_both_empty_returns_empty() -> None:
    assert reciprocal_rank_fusion([], []) == []


def test_appearing_in_both_lists_outranks_single() -> None:
    # "shared" is rank 2 in both lists; "top_vector" is rank 1 in vector only
    vector = ["top_vector", "shared"]
    text = ["top_text", "shared"]
    result = reciprocal_rank_fusion(vector, text)
    # "shared" gets two RRF scores summed, beating both single-list rank-1 items
    assert result[0] == "shared"
