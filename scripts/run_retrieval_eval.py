"""Scores vector-only retrieval over the answerable golden set and logs one MLflow run."""

from pathlib import Path
from typing import Any

import psycopg

from ruleslawyer.eval.golden_set import GoldenQuestion, load_golden_set
from ruleslawyer.eval.metrics import recall_at_k, reciprocal_rank
from ruleslawyer.eval.tracking import RunConfig, log_run
from ruleslawyer.ingest.embed import DEFAULT_MODEL, Embedder
from ruleslawyer.ingest.load import connect
from ruleslawyer.retrieval.search import search_vectors

GOLDEN_SET_PATH = Path("evals/golden_set.jsonl")
EXPERIMENT = "retrieval-baseline"
TOP_K = 5
CHUNK_SIZE = 400
OVERLAP = 50


def mean(values: list[float]) -> float:
    """Averages scores, 0.0 for an empty list rather than raising."""
    return sum(values) / len(values) if values else 0.0


def evaluate(
    questions: list[GoldenQuestion],
    retrieved_paths: list[list[str]],
    top_k: int,
) -> dict[str, float]:
    """Averages recall@k and reciprocal rank across the scored questions.

    Args:
        questions: the answerable golden questions, in the order they were scored.
        retrieved_paths: the heading paths each question retrieved, same order.
        top_k: the k for recall@k.

    Returns:
        Mean recall@k and mean reciprocal rank, keyed for MLflow.
    """
    # strict so a questions/paths length mismatch fails loudly, not silently truncated
    pairs = list(zip(questions, retrieved_paths, strict=True))
    recalls = [recall_at_k(paths, q.grounding, top_k) for q, paths in pairs]
    ranks = [reciprocal_rank(paths, q.grounding) for q, paths in pairs]
    return {"recall_at_k": mean(recalls), "mrr": mean(ranks)}


def retrieved_paths_for(
    question: GoldenQuestion,
    embedder: Embedder,
    conn: psycopg.Connection[Any],
    top_k: int,
) -> list[str]:
    """Runs one question through vector search and returns its heading paths, best first.

    Args:
        question: the golden question to search for.
        embedder: the process-wide Embedder.
        conn: open psycopg connection.
        top_k: how many results to retrieve.

    Returns:
        The heading path of each retrieved chunk, closest match first.
    """
    # a null edition searches both editions, which is right for edition-agnostic questions
    results = search_vectors(question.question, embedder, conn, question.edition, top_k)
    return [result.heading_path for result in results]


def main() -> None:
    """Scores the vector-only baseline over the answerable golden set and logs it to MLflow."""
    answerable = [q for q in load_golden_set(GOLDEN_SET_PATH) if q.answerable]
    embedder = Embedder()
    conn = connect()

    retrieved = [retrieved_paths_for(q, embedder, conn, TOP_K) for q in answerable]
    metrics = evaluate(answerable, retrieved, TOP_K)

    config = RunConfig(
        chunk_size=CHUNK_SIZE,
        overlap=OVERLAP,
        embedding_model=DEFAULT_MODEL,
        top_k=TOP_K,
        retrieval_mode="vector",
    )
    log_run(config, metrics, EXPERIMENT)

    print(f"scored {len(answerable)} answerable questions")
    for name, value in metrics.items():
        print(f"  {name}: {value:.3f}")


if __name__ == "__main__":
    main()
