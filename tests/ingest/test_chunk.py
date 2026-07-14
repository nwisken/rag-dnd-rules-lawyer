"""Tests the chunking of input text"""

import pytest
from src.ruleslawyer.ingest.types import Section, Chunk
from src.ruleslawyer.ingest.chunk import chunk_section

def count_words(text: str) -> int:
    return len(text.split())


 # factory for creating sections for testing
def make_section(text: str = "", heading_path: tuple[str, ...] = ("Combat",)) -> Section:
    return Section(heading_path=heading_path, text=text)

def make_chunk(
    content: str = "",
    heading_path: tuple[str, ...] = ("Combat",),
    doc_section: str = "Combat",
    page_ref: str | None = None,
    token_count: int = 0,
) -> Chunk:
    return Chunk(
        content=content,
        heading_path=heading_path,
        doc_section=doc_section,
        page_ref=page_ref,
        token_count=token_count,
    )

def test_chunking_with_empty_text():
    """checks chunking handles empty text correctly"""
    result = chunk_section(make_section(),count_words)
    assert result == [] # no chunks with no errors raised


def test_fits_in_one_chunk():
    """checks fits in one chunk correctly"""



def test_chunking_with_empy_heading_path():
    """checks chunking handles empty headings correctly"""
    result = chunk_section(make_section(text="blah blah blah", heading_path=(),),count_words)
    assert result == [make_chunk(content="blah blah blah",heading_path=(),doc_section="", token_count=3),]