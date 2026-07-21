"""Diagnostic for the corpus-integrity checks in verify_corpus.

Runs the pass/fail verification, then answers the question the score alone cannot:
of the PDF shingles that are NOT in the markdown, how many are missing content
versus PDF-extraction noise? Sampling them is what justifies pinning
CONTAINMENT_THRESHOLD to a number instead of guessing.
"""

import random
from pathlib import Path

from verify_corpus import (
    extract_pdf_text,
    is_corpus_valid,
    normalize,
    shingles,
)

PDF_PATH = Path("data/raw/SRD_CC_v5.1.pdf")
MARKDOWN_PATH = Path("data/raw/SRD_CC_v5.1.md")

SAMPLE_SIZE = 25
SEED = 0  # fixed so two runs of this script are comparable


def unmatched_shingles(pdf_text: str, markdown_text: str) -> set[tuple[str, ...]]:
    """PDF shingles with no counterpart in the markdown -- the missing 1 - containment.

    Args:
        pdf_text: raw text extracted from the source PDF.
        markdown_text: full text of the markdown corpus.

    Returns:
        set[tuple[str, ...]]: shingles present in the PDF but absent from the markdown.
    """
    pdf_shingles = shingles(normalize(pdf_text))
    markdown_shingles = shingles(normalize(markdown_text))
    return pdf_shingles - markdown_shingles


def is_footer(shingle: tuple[str, ...]) -> bool:
    """Whether a shingle straddles the PDF's running "System Reference Document" footer.

    Args:
        shingle: one normalized shingle.

    Returns:
        bool: True if the footer's words all appear in the shingle.
    """
    return "system" in shingle and "reference" in shingle and "document" in shingle


def has_fragment(shingle: tuple[str, ...]) -> bool:
    """Whether a shingle contains a word split by PDF extraction ("writ ing", "lev el").

    A crude proxy: real SRD prose rarely puts a one- or two-letter word mid-sentence,
    so a short token usually means the extractor broke a longer word in half.

    Args:
        shingle one normalized shingle.

    Returns:
        bool: True if any token is two characters or fewer.
    """
    return any(len(token) <= 2 for token in shingle)


def main() -> None:
    """Run the verification, then sample and categorise unmatched shingles."""
    print("=== verification ===")
    print("RESULT:", is_corpus_valid(PDF_PATH, MARKDOWN_PATH))

    pdf_text = extract_pdf_text(PDF_PATH)
    markdown_text = MARKDOWN_PATH.read_text(encoding="utf-8")

    unmatched = unmatched_shingles(pdf_text, markdown_text)
    total = len(shingles(normalize(pdf_text)))
    print(f"\n=== unmatched shingles: {len(unmatched)} of {total} ===")

    # How much of the shortfall is provably extraction noise rather than lost content?
    footer = sum(1 for shingle in unmatched if is_footer(shingle))
    fragment = sum(1 for shingle in unmatched if has_fragment(shingle))
    either = sum(1 for shingle in unmatched if is_footer(shingle) or has_fragment(shingle))
    count = len(unmatched)
    print(f"  running-footer contamination : {footer} ({footer / count:.1%})")
    print(f"  split-word fragments         : {fragment} ({fragment / count:.1%})")
    print(f"  either                       : {either} ({either / count:.1%})")

    # The remainder is mostly stat blocks and spell tables, which the PDF lays out in
    # columns and pypdf flattens in reading order -- same facts, different word order,
    # so no 8-gram can line up. Eyeball the sample to confirm that still holds.
    print(f"\n=== sample of {SAMPLE_SIZE} unmatched shingles ===")
    # sorted() first so the sample does not depend on set iteration order
    sample = random.Random(SEED).sample(sorted(unmatched), min(SAMPLE_SIZE, len(unmatched)))
    for shingle in sample:
        print("  " + " ".join(shingle))


if __name__ == "__main__":
    main()
