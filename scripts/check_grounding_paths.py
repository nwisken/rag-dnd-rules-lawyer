"""Reports which golden-set grounding paths match no heading_path in the database."""

from typing import Any

import psycopg


def is_grounded_by(heading_path: str, grounding: str) -> bool:
    """Tests whether a heading path sits at or below a grounding path in the tree.

    Args:
        heading_path: a chunk's full heading path, e.g "Cover > Half Cover".
        grounding: a grounding path from the golden set, e.g "Cover".

    Returns:
        True if heading_path is the grounding section or one nested under it.
    """
    return heading_path == grounding or heading_path.startswith(grounding + " > ")


def fetch_heading_paths(conn: psycopg.Connection[Any]) -> set[str]:
    """query pulling distinct heading_paths out of Postgres

    Args:
        conn: connection to Postgres database

    Returns: 
        a set of heading_paths
    """

    sql = "SELECT DISTINCT heading_path FROM chunks WHERE heading_path IS NOT NULL"
    with conn.cursor() as cur:
        result = cur.execute(sql).fetchall()

    return {row[0] for row in result}