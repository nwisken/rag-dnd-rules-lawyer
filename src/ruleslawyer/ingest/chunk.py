"""Module for the chunking functions of text."""
import pysbd

from ruleslawyer.ingest.types import Chunk, Section, TokenCounter

_segmenter = pysbd.Segmenter(language="en", clean=False)


def split_sentences(paragraph: str) -> list[str]:
    """Splits a paragraph into sentences.

    Uses pysbd (rule-based, no model download) rather than
     a REGEX or similar methodology.
    """
    sentences: list[str] = _segmenter.segment(paragraph)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def build_chunk(
    chunks: list[Chunk],
    processed_text: list[str],
    section: Section,
    count_tokens: TokenCounter,
) -> None:
    """Builds a chunk from the paragraphs collected so far and adds it to chunks.

    Args:
        chunks: list of finished chunks, appended to in place.
        processed_text: paragraphs making up the chunk being built.
        section: the section the paragraphs came from.
        count_tokens: function that returns the token count of a string.
    """
    content = "\n\n".join(processed_text)
    chunks.append(
        Chunk(
            content=content,
            heading_path=section.heading_path,
            doc_section=section.heading_path[0] if section.heading_path else "",
            page_ref=None,  # using Markdown files with no page number for the moment
            token_count=count_tokens(content),
        )
    )


def overlap_tail(
    processed_text: list[str],
    count_tokens: TokenCounter,
    overlap_tokens: int,
) -> list[str]:
    """Takes paragraphs from the end of a finished chunk to start the next one with.

    Walks backwards from the tail.  Stops once ~overlap_tokens have been collected.

    Args:
        processed_text: paragraphs of the chunk that was just banked.
        count_tokens: function that returns the token count of a string.
        overlap_tokens: how many tokens of tail to carry into the next chunk.
    """
    if overlap_tokens <= 0:
        return []
    tail: list[str] = []
    tail_tokens = 0
    for paragraph in reversed(processed_text):
        # always take at least one paragraph, then stop once we have enough
        if tail and tail_tokens + count_tokens(paragraph) > overlap_tokens:
            break
        tail.insert(0, paragraph)  # insert at front to keep the original order
        tail_tokens += count_tokens(paragraph)
    return tail


def chunk_section(
    section: Section,
    count_tokens: TokenCounter,
    max_tokens: int = 400,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Chunks a section ready for embedding.

    Args:
        section: Section dataclass to chunk.
        count_tokens: function that returns the token count of a string.
        max_tokens: max number of tokens allowed in a chunk.
        overlap_tokens: number of tokens to overlap between chunks.
    """
    raw_text = section.text.strip()
    if not raw_text:  # nothing to chunk
        return []
    
    # split any paragraph that is too big to in a chunk into sentences
    paragraphs: list[str] = []
    raw_paragraphs = raw_text.split("\n\n")
    for raw_paragraph in raw_paragraphs:
        if count_tokens(raw_paragraph) > max_tokens:
            paragraphs.extend(split_sentences(raw_paragraph))
        else:
            paragraphs.append(raw_paragraph)

    # keep the overlap under the budget, or a carried-over tail could fill a whole
    # chunk on its own and the loop would never make progress
    overlap = min(overlap_tokens, max_tokens - 1)

    chunks: list[Chunk] = []  # finished chunks
    processed_text: list[str] = []  # paragraphs added to the chunk being built
    current_tokens = 0
    for paragraph in paragraphs:
        paragraph_tokens = count_tokens(paragraph)
        if current_tokens + paragraph_tokens > max_tokens:  # New chunk created
            build_chunk(chunks, processed_text, section, count_tokens)
            # start the next chunk with the tail of the one just banked
            processed_text = overlap_tail(processed_text, count_tokens, overlap)
            current_tokens = count_tokens("\n\n".join(processed_text)) if processed_text else 0
        processed_text.append(paragraph)
        current_tokens += paragraph_tokens

    if processed_text:  # any text leftover not currently in a chunk
        build_chunk(chunks, processed_text, section, count_tokens)
    return chunks


def chunk_sections(
    sections: list[Section],
    count_tokens: TokenCounter,
    max_tokens: int = 400,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Chunks every section, keeping them in order.

    Args:
        sections: the sections to chunk.
        count_tokens: function that returns the token count of a string.
        max_tokens: max number of tokens allowed in a chunk.
        overlap_tokens: number of tokens to overlap between chunks.
    """
    chunks: list[Chunk] = []
    for section in sections:
        chunks.extend(chunk_section(section, count_tokens, max_tokens, overlap_tokens))
    return chunks
