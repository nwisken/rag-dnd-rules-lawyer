"""Naive vector search over the chunks table."""

from dataclasses import dataclass
from typing import Any

import psycopg
from pgvector import Vector

from ruleslawyer.ingest.embed import Embedder


@dataclass
class SearchResult:
    content: str
    score: float
    edition: str
    doc_section: str
    heading_path: str
    page_ref: str | None


def search_vectors(
    query: str,
    embedder: Embedder,
    conn: psycopg.Connection[Any],
    edition: str | None = None,
    top_k: int = 5,
) -> list[SearchResult]:
    """Embed a query and return the top-k closest chunks by cosine distance.

    Args:
        query: natural-language question from the user.
        embedder: reuse the process-wide Embedder instance.
        conn: open psycopg connection with pgvector registered.
        edition: if set, only search this edition ('srd51' or 'srd52').
        top_k: how many results to return.

    Returns:
        Results ordered by ascending cosine distance (best match first).
    """
    query_vector = embedder.embed_texts([query])[0]

    sql = (
        "SELECT content, embedding <=> %s AS distance,"
        " edition, doc_section, heading_path, page_ref"
        " FROM chunks"
    )
    params: list[Any] = [Vector(query_vector)]

    if edition is not None:
        sql += " WHERE edition = %s"
        params.append(edition)

    sql += " ORDER BY distance ASC LIMIT %s"
    params.append(top_k)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        SearchResult(
            content=row[0],
            score=row[1],
            edition=row[2],
            doc_section=row[3],
            heading_path=row[4],
            page_ref=row[5],
        )
        for row in rows
    ]
