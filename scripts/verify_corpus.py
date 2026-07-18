"""Module for verifying that the markdown files match the contents of the PDF rules."""


import unicodedata
from pathlib import Path

from nltk.tokenize import wordpunct_tokenize
from pypdf import PdfReader


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

