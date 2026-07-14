"""Tests the chunking of input text"""

from ruleslawyer.ingest.chunk import chunk_section, chunk_sections
from ruleslawyer.ingest.types import Chunk, Section


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
        doc_section=doc_section,fixed test file for chunk and added adit        page_ref=page_ref,
        token_count=token_count,
    )

def test_chunking_with_empty_text():
    """checks chunking handles empty text correctly"""
    result = chunk_section(make_section(),count_words)
    assert result == [] # no chunks with no errors raised


def test_fits_in_one_chunk():
    """checks a section under the budget comes back as a single chunk"""
    result = chunk_section(make_section(text="a short sentence here"), count_words)
    assert result == [make_chunk(content="a short sentence here", token_count=4)]



def test_chunking_with_empy_heading_path():
    """checks chunking handles empty headings correctly"""
    result = chunk_section(make_section(text="blah blah blah", heading_path=()), count_words)
    assert result == [
        make_chunk(content="blah blah blah", heading_path=(), doc_section="", token_count=3),
    ]


def test_overlap_carried_into_next_chunk():
    """checks the tail of a full chunk is repeated at the start of the next one"""
    paragraphs = [
        "para one has five words",  # 5 tokens each, so 2 fit in a 12 token budget
        "para two has five words",
        "para three has five words",
        "para four has five words",
    ]
    section = make_section(text="\n\n".join(paragraphs))

    result = chunk_section(section, count_words, max_tokens=12, overlap_tokens=5)

    # each chunk repeats the last paragraph of the one before it
    assert [chunk.content for chunk in result] == [
        "para one has five words\n\npara two has five words",
        "para two has five words\n\npara three has five words",
        "para three has five words\n\npara four has five words",
    ]


def test_no_chunk_exceeds_max_tokens():
    """checks the token budget is never blown, even with overlap carried over"""
    paragraphs = [f"para {i} has five words" for i in range(10)]
    section = make_section(text="\n\n".join(paragraphs))

    result = chunk_section(section, count_words, max_tokens=12, overlap_tokens=5)

    assert result  # it actually produced chunks
    for chunk in result:
        assert chunk.token_count <= 12


def test_oversized_paragraph_is_split_into_sentences():
    """checks one huge paragraph is broken on sentence boundaries, not mid-sentence"""
    # one paragraph, three sentences, 6 tokens each. pysbd must not split on "30 ft."
    paragraph = (
        "You can move up to 30 ft. "
        "The target must make a save. "
        "A hit deals eight fire damage."
    )
    section = make_section(text=paragraph)

    result = chunk_section(section, count_words, max_tokens=8, overlap_tokens=0)

    # the paragraph was too big for one chunk, so it was split on sentence ends
    assert len(result) == 3
    assert result[0].content == "You can move up to 30 ft."
    assert result[1].content == "The target must make a save."
    assert result[2].content == "A hit deals eight fire damage."


def test_chunk_sections_keeps_order_and_headings():
    """checks chunk_sections chunks every section and preserves each heading path"""
    sections = [
        make_section(text="combat text here", heading_path=("Combat",)),
        make_section(text="spell text here", heading_path=("Spellcasting", "Slots")),
    ]

    result = chunk_sections(sections, count_words)

    assert [chunk.content for chunk in result] == ["combat text here", "spell text here"]
    assert [chunk.heading_path for chunk in result] == [("Combat",), ("Spellcasting", "Slots")]
    assert [chunk.doc_section for chunk in result] == ["Combat", "Spellcasting"]