"""Module for verifying that the markdown files match the contents of the PDF rules."""


import unicodedata

from nltk.tokenize import wordpunct_tokenize


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

    