"""Module for verifying that the markdown files match the contents of the PDF rules."""


import unicodedata
from pathlib import Path

from nltk.tokenize import wordpunct_tokenize
from pypdf import PdfReader

# Anchor sections that must be present in the corpus, one per major SRD 5.1 chapter.
# Verified to occur in the PDF's normalized text (never derived from the markdown --
# expectations taken from the file under test would prove nothing).
EXPECTED_SECTIONS = [
    "Races",
    "Beyond 1st Level",
    "Multiclassing",
    "Backgrounds",
    "Equipment",
    "Feats",
    "Using Ability Scores",
    "The Environment",
    "Between Adventures",
    "The Order of Combat",
    "Making an Attack",
    "Damage and Healing",
    "Spellcasting",
    "Spell Lists",
    "Spell Descriptions",
    "Traps",
    "Magic Items",
    "Sentient Magic Items",
    "Monsters",
    "The Planes of Existence",
    "Nonplayer Characters",
]

# Every anchor is a hand-verified chapter, so a missing one is a real failure:
# no tolerance. Kept as a dial rather than inlined so the choice stays visible.
SECTION_COVERAGE = 100
# Measured 0.8065 on the pinned SRD 5.1 pair (2026-07-21). The shortfall is PDF
# extraction noise, not lost rules -- ~76% of unmatched shingles provably so, see
# scripts/diagnose_corpus.py -- so 0.8065 is near the ceiling for a good corpus.
# Pinned below it with margin for an extractor version bump, not for random variation:
# both inputs are fixed, so the score is deterministic. This is a tripwire for a
# swapped or re-pinned corpus. Revisable only with a fresh measurement.
CONTAINMENT_THRESHOLD = 0.75


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract the full text of a PDF as one string, pages joined by newlines.

    Args:
        pdf_path (Path): path to the source PDF.

    Returns:
        str: concatenated text of every page.
    """
    reader = PdfReader(pdf_path)
    pages = [page.extract_text() for page in reader.pages]
    return "\n".join(pages)


def normalize(text: str) -> list[str]:
    """Raw text -> lowercase alphabetic words, ready for shingling.

    Args:
        text (str): The raw text to be normalized.

    Returns:
        list[str]: The normalized text in tokens
    """
  
    # remove PDF ligatures
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    # tokenize
    text_tokens = wordpunct_tokenize(text)
    # only keep alphabetic characters
    text_tokens_alpha = [token for token in text_tokens if token.isalpha()]
    return text_tokens_alpha


def shingles(words: list[str], n: int = 8) -> set[tuple[str, ...]]:
    """uses w-shingling on normalised tokens.

    Args:
        words (list[str]): list of tokens to be shingled
        n (int): number of shinglings to use

    Returns:
        set[tuple[str, ...]]: shingled tokens ready for comparison
        """

    result = set()
    for i in range(len(words)+1-n):
        result.add(tuple(words[i:i+n]))

    return result


def containment(reference: set[tuple[str, ...]], candidate: set[tuple[str, ...]]) -> float:
    """Checks the similarity between the reference and the candidate sets.

    Args:
        reference: reference set
        candidate: candidate set

    :Returns
        float: similarity score
    """
    same_text_length = len(candidate.intersection(reference))
    return same_text_length / len(reference)


def missing_sections(markdown_text: str) -> list[str]:
    """Check A: which EXPECTED_SECTIONS have no heading in the markdown.

    Only top-level ("# ") heading lines count. Body prose is not evidence that the
    section survived, and neither are deeper headings: "### Equipment" occurs a dozen
    times inside Backgrounds, so accepting any level let a corpus missing the whole
    Equipment chapter pass. Matching is substring-within-heading rather than equality
    because some anchors sit under an "Appendix ..." prefix.

    Args:
        markdown_text: full text of the markdown corpus.

    Returns:
        list[str]: expected sections with no matching heading, empty if all present.
    """
    heading_lines = [line for line in markdown_text.splitlines() if line.startswith("# ")]
    return [
        header
        for header in EXPECTED_SECTIONS
        if not any(header in line for line in heading_lines)
    ]


def corpus_containment(pdf_text: str, markdown_text: str) -> float:
    """Check B: fraction of the PDF's 8-shingles that appear in the markdown.

    Args
        pdf_text: raw text extracted from the source PDF.
        markdown_text: full text of the markdown corpus.

    Returns:
        float: containment score in [0, 1].
    """
    pdf_shingles = shingles(normalize(pdf_text))
    markdown_shingles = shingles(normalize(markdown_text))

    # containment divides by len(reference); guarantee a non-empty reference here,
    # where the shingles are built, rather than inside the pure maths.
    assert pdf_shingles, "No shingles extracted from the PDF -- unreadable?"

    return containment(pdf_shingles, markdown_shingles)


def is_corpus_valid(pdf_path: Path, markdown_path: Path) -> bool:
    """Checks if the markdown file matches the contents of the PDF rules.

    Args:
        pdf_path: path to the source PDF.
        markdown_path: path to the markdown file.

    Returns:
        bool: True if the markdown file matches the contents of the PDF rules.
    """

    pdf_file = extract_pdf_text(pdf_path)
    markdown_file = markdown_path.read_text(encoding="utf-8")

    # check A, That the expected Headers are inside the markdown file
    missing = missing_sections(markdown_file)

    count = len(EXPECTED_SECTIONS) - len(missing)
    section_coverage = count / len(EXPECTED_SECTIONS) * 100
    total = len(EXPECTED_SECTIONS)
    print(f"Check A -- section coverage: {section_coverage:.1f}% ({count}/{total})")
    if missing:
        print(f"  missing sections: {', '.join(missing)}")
    if section_coverage < SECTION_COVERAGE:
        print("Section coverage % less than Threshold")
        return False

    # Check B, that the shingle containment meets the threshold
    containment_value = corpus_containment(pdf_file, markdown_file)
    print(f"Check B -- containment: {containment_value:.4f} (threshold {CONTAINMENT_THRESHOLD})")
    if containment_value >= CONTAINMENT_THRESHOLD:
        return True
    else:
        print("Containment less than Threshold")
        return False




