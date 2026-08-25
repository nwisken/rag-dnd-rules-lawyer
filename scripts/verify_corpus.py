"""Module for verifying that the markdown files match the contents of the PDF rules."""


import unicodedata
from pathlib import Path

from nltk.tokenize import wordpunct_tokenize
from pypdf import PdfReader

# Anchor sections per edition, verified against each PDF's normalized text (never
# derived from the markdown -- expectations taken from the file under test would
# prove nothing).
EXPECTED_SECTIONS_51 = [
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

EXPECTED_SECTIONS_52 = [
    "Playing the Game",
    "Character Creation",
    "Classes",
    "Character Origins",
    "Feats",
    "Equipment",
    "Spells",
    "Rules Glossary",
    "Gameplay Toolbox",
    "Magic Items",
    "Monsters",
]

EXPECTED_SECTIONS_BY_EDITION: dict[str, list[str]] = {
    "srd51": EXPECTED_SECTIONS_51,
    "srd52": EXPECTED_SECTIONS_52,
}

# Every anchor is a hand-verified chapter, so a missing one is a real failure:
# no tolerance. Kept as a dial rather than inlined so the choice stays visible.
SECTION_COVERAGE = 100
# Containment thresholds per edition, pinned below the measured score with margin.
# SRD 5.1 measured 0.8065 (2026-07-21); SRD 5.2 measured 0.7196 (2026-08-25).
# Shortfall is PDF extraction noise, not lost rules. Revisable only with a fresh
# measurement — see scripts/diagnose_corpus.py.
CONTAINMENT_THRESHOLD_BY_EDITION: dict[str, float] = {
    "srd51": 0.75,
    "srd52": 0.65,
}


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


def missing_sections(markdown_text: str, edition: str) -> list[str]:
    """Check A: which expected sections have no heading in the markdown.

    Only top-level ("# ") heading lines count. Body prose is not evidence that the
    section survived, and neither are deeper headings: "### Equipment" occurs a dozen
    times inside Backgrounds, so accepting any level let a corpus missing the whole
    Equipment chapter pass. Matching is substring-within-heading rather than equality
    because some anchors sit under an "Appendix ..." prefix.

    Args:
        markdown_text: full text of the markdown corpus.
        edition: 'srd51' or 'srd52', selects the expected-sections list.

    Returns:
        list[str]: expected sections with no matching heading, empty if all present.
    """
    expected = EXPECTED_SECTIONS_BY_EDITION[edition]
    heading_lines = [line for line in markdown_text.splitlines() if line.startswith("# ")]
    return [
        header
        for header in expected
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


def is_corpus_valid(pdf_path: Path, markdown_path: Path, edition: str = "srd51") -> bool:
    """Checks if the markdown file matches the contents of the PDF rules.

    Args:
        pdf_path: path to the source PDF.
        markdown_path: path to the markdown file.
        edition: 'srd51' or 'srd52', selects the expected-sections list.

    Returns:
        bool: True if the markdown file matches the contents of the PDF rules.
    """

    pdf_file = extract_pdf_text(pdf_path)
    markdown_file = markdown_path.read_text(encoding="utf-8")

    expected = EXPECTED_SECTIONS_BY_EDITION[edition]

    # check A, That the expected Headers are inside the markdown file
    missing = missing_sections(markdown_file, edition)

    count = len(expected) - len(missing)
    section_coverage = count / len(expected) * 100
    total = len(expected)
    print(f"Check A -- section coverage: {section_coverage:.1f}% ({count}/{total})")
    if missing:
        print(f"  missing sections: {', '.join(missing)}")
    if section_coverage < SECTION_COVERAGE:
        print("Section coverage % less than Threshold")
        return False

    # Check B, that the shingle containment meets the threshold
    threshold = CONTAINMENT_THRESHOLD_BY_EDITION[edition]
    containment_value = corpus_containment(pdf_file, markdown_file)
    print(f"Check B -- containment: {containment_value:.4f} (threshold {threshold})")
    if containment_value >= threshold:
        return True
    else:
        print("Containment less than Threshold")
        return False




