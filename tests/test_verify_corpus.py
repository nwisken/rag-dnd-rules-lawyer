"""Tests the pure functions of the corpus verifier (no PDF/IO)."""

from scripts.verify_corpus import (
    EXPECTED_SECTIONS,
    containment,
    missing_sections,
    normalize,
    shingles,
)


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


def test_missing_sections_empty_when_all_anchors_present() -> None:
    """checks a corpus with every anchor as a top-level heading reports nothing missing."""
    markdown = "\n".join(f"# {section}\n\nbody text\n" for section in EXPECTED_SECTIONS)
    assert missing_sections(markdown) == []


def test_missing_sections_ignores_deeper_headings() -> None:
    """checks a sub-heading does not satisfy an anchor — the regression that let a
    corpus missing the whole Equipment chapter pass, because '### Equipment' occurs
    a dozen times inside Backgrounds."""
    markdown = "# Races\n\n### Equipment\n\nstarting gear for this background\n"
    assert "Equipment" in missing_sections(markdown)


def test_missing_sections_ignores_body_prose() -> None:
    """checks naming a section in a paragraph is not evidence the section survived."""
    markdown = "# Races\n\nSee the Equipment chapter for starting gear.\n"
    assert "Equipment" in missing_sections(markdown)


def test_missing_sections_accepts_prefixed_headings() -> None:
    """checks substring matching, so anchors living under an 'Appendix ...' title count."""
    markdown = "# Appendix PH-C: The Planes of Existence\n"
    assert "The Planes of Existence" not in missing_sections(markdown)
