"""Shared types for the ingest pipeline."""

from collections.abc import Callable
from dataclasses import dataclass

TokenCounter = Callable[[str], int]
"""Counts tokens in a string. Injected so chunking logic never imports a tokenizer."""


@dataclass(frozen=True, slots=True)
class Section:
    """A leaf section of the SRD: one heading and the prose under it."""

    heading_path: tuple[str, ...]
    text: str


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrieval unit ready for embedding and DB insertion."""

    content: str
    heading_path: tuple[str, ...]
    doc_section: str
    page_ref: str | None
    token_count: int
