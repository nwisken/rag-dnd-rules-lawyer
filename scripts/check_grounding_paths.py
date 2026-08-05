"""Reports which golden-set grounding paths match no heading_path in the database."""

from pathlib import Path
from typing import Any

import psycopg

from ruleslawyer.eval.golden_set import GoldenQuestion, load_golden_set
from ruleslawyer.ingest.load import connect

GOLDEN_SET_PATH = Path("evals/golden_set.jsonl")


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


def unmatched_grounding(questions: list[GoldenQuestion], heading_paths: set[str]) -> list[str]:
    """Finds grounding paths in the golden set that no chunk in the database sits under.

    Args:
        questions: the loaded golden set.
        heading_paths: every unique heading path in the chunks table.

    Returns:
        Each unmatched grounding path, in question order, with duplicates kept.
    """

    results = []
    for question in questions:
        for grounding in question.grounding:
            if not any(is_grounded_by(path, grounding) for path in heading_paths):
                results.append(grounding)

    return results


def main() -> None:
    """Reports every golden-set grounding path with no matching chunk in the database."""
    questions = load_golden_set(GOLDEN_SET_PATH)
    conn = connect()
    heading_paths = fetch_heading_paths(conn)

    unmatched = unmatched_grounding(questions, heading_paths)
    total = sum(len(question.grounding) for question in questions)

    print(f"{len(heading_paths)} distinct heading paths in the database")
    print(f"{total - len(unmatched)}/{total} grounding paths matched")
    for grounding in unmatched:
        print(f"  unmatched: {grounding}")


if __name__ == "__main__":
    main()
