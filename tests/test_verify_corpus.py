"""Tests the pure functions of the corpus verifier (no PDF/IO)."""

from scripts.verify_corpus import containment, normalize, shingles


def test_normalize_lowercases_strips_digits_and_flattens_ligatures() -> None:
    """checks the three jobs at once: NFKC ligature, digit drop, lowercase."""
    assert normalize("Take 8d6 ﬁre damage!") == ["take", "fire", "damage"]


def test_normalize_drops_punctuation_only_tokens() -> None:
    """checks standalone punctuation never survives as a token."""
    assert normalize("a -- b, c.") == ["a", "b", "c"]


def test_shingles_counts_every_window() -> None:
    """checks 10 words at n=8 yields 3 windows, including the last one."""
    words = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    result = shingles(words, n=8)
    assert len(result) == 3
    assert tuple(words[2:10]) in result


def test_shingles_len_equals_n_yields_one() -> None:
    """checks the edge case where the word count equals the window size."""
    words = ["a", "b", "c", "d", "e", "f", "g", "h"]
    assert len(shingles(words, n=8)) == 1


def test_shingles_returns_a_set_of_tuples() -> None:
    """checks dedup (set) and hashable windows (tuple) — both load-bearing."""
    result = shingles(["a", "b", "a", "b", "a"], n=2)
    assert result == {("a", "b"), ("b", "a")}
    assert all(isinstance(shingle, tuple) for shingle in result)


def test_containment_perfect_match_is_one() -> None:
    """checks identical content scores 1.0."""
    ref: set[tuple[str, ...]] = {("a", "b"), ("c", "d")}
    assert containment(ref, ref) == 1.0


def test_containment_measures_reference_survival_not_candidate() -> None:
    """checks direction: a candidate missing half the reference scores 0.5,
    and extra shingles in the candidate never inflate the score."""
    reference: set[tuple[str, ...]] = {("a", "b"), ("c", "d")}
    candidate: set[tuple[str, ...]] = {("a", "b"), ("x", "y"), ("z", "w")}
    assert containment(reference, candidate) == 0.5
