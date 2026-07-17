"""Tests the model-free parts of embedding (no Embedder here: it downloads ~130 MB)"""

from ruleslawyer.ingest.embed import embedding_input
from ruleslawyer.ingest.types import Chunk


def make_chunk(content: str, heading_path: tuple[str, ...]) -> Chunk:
    return Chunk(
        content=content,
        heading_path=heading_path,
        doc_section=heading_path[0] if heading_path else "",
        page_ref=None,
        token_count=0,
    )


def test_embedding_input_prepends_heading_path() -> None:
    """checks the embedded string is the ' > '-joined path, a blank line, then content"""
    chunk = make_chunk("You can move up to 30 ft.", ("Combat", "Making an Attack"))
    assert embedding_input(chunk) == "Combat > Making an Attack\n\nYou can move up to 30 ft."


def test_embedding_input_with_empty_path_is_bare_content() -> None:
    """checks an empty heading path adds no separator junk before the content"""
    chunk = make_chunk("license preamble text", ())
    assert embedding_input(chunk) == "license preamble text"
