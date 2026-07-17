"""Load chunks and their embeddings into the Postgres chunks table."""

from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from pydantic_settings import BaseSettings, SettingsConfigDict

from ruleslawyer.ingest.types import Chunk


class Settings(BaseSettings):
    """Connection settings, read from the environment (or .env for local dev)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://ruleslawyer:ruleslawyer@localhost:5432/ruleslawyer"


def connect(database_url: str | None = None) -> psycopg.Connection[Any]:
    """Opens a connection with pgvector's type adapter registered.

    Args:
        database_url: overrides the environment-derived URL (mainly for tests).

    Returns:
        An open psycopg connection that can send and receive vector values.
    """
    url = database_url or Settings().database_url
    conn = psycopg.connect(url)
    register_vector(conn)
    return conn


def load_chunks(
    conn: psycopg.Connection[Any],
    chunks: list[Chunk],
    embeddings: list[list[float]],
    edition: str,
) -> int:
    """Replaces one edition's rows with these chunks and their embeddings.

    Deletes the edition's existing rows first so re-running ingest is
    idempotent, then inserts everything in one transaction.

    Args:
        conn: open connection from connect().
        chunks: the chunks to store, in order.
        embeddings: one vector per chunk, same order as chunks.
        edition: 'srd51' or 'srd52'; stamped on every inserted row.

    Returns:
        The number of rows inserted.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(f"{len(chunks)} chunks but {len(embeddings)} embeddings")
    delete_sql = "DELETE from chunks WHERE edition = %s"
    conn.execute(delete_sql, (edition,))

    insert_sql = (
        "INSERT INTO chunks"
        " (content, embedding, edition, doc_section, heading_path, page_ref, token_count)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    rows = []
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        rows.append(
            (
                chunk.content,
                Vector(embedding),
                edition,
                chunk.doc_section,
                " > ".join(chunk.heading_path),
                chunk.page_ref,
                chunk.token_count,
            )
        )
    with conn.cursor() as cur:
        cur.executemany(insert_sql, rows)
        inserted = cur.rowcount

    conn.commit()
    return inserted
