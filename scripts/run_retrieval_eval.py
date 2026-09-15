"""Scores retrieval over the answerable golden set and logs one MLflow run.

Usage:
    uv run python scripts/run_retrieval_eval.py vector
    uv run python scripts/run_retrieval_eval.py hybrid --chunk-size 200 --overlap 25
    uv run python scripts/run_retrieval_eval.py hybrid --model all-MiniLM-L6-v2
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import psycopg

from ruleslawyer.eval.golden_set import GoldenQuestion, load_golden_set
from ruleslawyer.eval.metrics import recall_at_k, reciprocal_rank
from ruleslawyer.eval.tracking import RunConfig, log_run
from ruleslawyer.ingest.embed import DEFAULT_MODEL, Embedder
from ruleslawyer.ingest.load import connect
from ruleslawyer.retrieval.fusion import reciprocal_rank_fusion
from ruleslawyer.retrieval.search import search_text, search_vectors

GOLDEN_SET_PATH = Path("evals/golden_set.jsonl")
BASELINES_PATH = Path("evals/baselines.json")
DEFAULT_EXPERIMENT = "retrieval-baseline"
TOP_K = 5


def check_gate(mode: str, metrics: dict[str, float]) -> None:
    """Fails the process if recall@k regressed past the tracked baseline (for CI).

    Args:
        mode: retrieval mode being gated; must have a baseline entry.
        metrics: the just-computed metrics for this run.
    """
    baseline = json.loads(BASELINES_PATH.read_text())
    if mode not in baseline["retrieval"]:
        print(f"GATE FAIL: no baseline for mode {mode!r} in {BASELINES_PATH}")
        sys.exit(1)
    base_recall = baseline["retrieval"][mode]["recall_at_k"]
    tolerance = baseline["tolerance"]
    floor = base_recall - tolerance
    actual = metrics["recall_at_k"]
    if actual < floor:
        print(f"GATE FAIL: recall_at_k {actual:.3f} < floor {floor:.3f} "
              f"(baseline {base_recall} - tol {tolerance})")
        sys.exit(1)
    print(f"GATE PASS: recall_at_k {actual:.3f} >= floor {floor:.3f}")


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


def retrieved_paths_for_text(
    question: GoldenQuestion,
    conn: psycopg.Connection[Any],
    top_k: int,
) -> list[str]:
    """Runs one question through full-text search and returns its heading paths, best first.

    Args:
        question: the golden question to search for.
        conn: open psycopg connection.
        top_k: how many results to retrieve.

    Returns:
        The heading path of each retrieved chunk, highest ts_rank_cd first.
    """
    results = search_text(question.question, conn, question.edition, top_k)
    return [result.heading_path for result in results]


def retrieved_paths_for_hybrid(
    question: GoldenQuestion,
    embedder: Embedder,
    conn: psycopg.Connection[Any],
    top_k: int,
) -> list[str]:
    """Runs both searches, fuses with RRF, returns the top-k heading paths.

    Args:
        question: the golden question to search for.
        embedder: the process-wide Embedder.
        conn: open psycopg connection.
        top_k: how many results to retrieve from each searcher before fusing.

    Returns:
        The heading paths from the fused ranking, best first, trimmed to top_k.
    """
    vector_paths = retrieved_paths_for(question, embedder, conn, top_k)
    text_paths = retrieved_paths_for_text(question, conn, top_k)
    return reciprocal_rank_fusion(vector_paths, text_paths)[:top_k]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score retrieval and log to MLflow.")
    parser.add_argument("mode", nargs="?", default="vector",
                        choices=["vector", "fulltext", "hybrid"],
                        help="retrieval mode (default: vector)")
    parser.add_argument("--chunk-size", type=int, default=400,
                        help="chunk size used during ingestion (default: 400)")
    parser.add_argument("--overlap", type=int, default=50,
                        help="overlap used during ingestion (default: 50)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"embedding model used during ingestion (default: {DEFAULT_MODEL})")
    parser.add_argument("--experiment", type=str, default=DEFAULT_EXPERIMENT,
                        help=f"MLflow experiment name (default: {DEFAULT_EXPERIMENT})")
    parser.add_argument("--gate", action="store_true",
                        help="exit non-zero if recall@k regressed past the tracked baseline (CI)")
    return parser.parse_args()


def main() -> None:
    """Scores retrieval over the answerable golden set and logs it to MLflow."""
    args = parse_args()
    answerable = [q for q in load_golden_set(GOLDEN_SET_PATH) if q.answerable]
    conn = connect()

    if args.mode == "vector":
        embedder = Embedder(model_name=args.model)
        retrieved = [retrieved_paths_for(q, embedder, conn, TOP_K) for q in answerable]
    elif args.mode == "fulltext":
        retrieved = [retrieved_paths_for_text(q, conn, TOP_K) for q in answerable]
    elif args.mode == "hybrid":
        embedder = Embedder(model_name=args.model)
        retrieved = [retrieved_paths_for_hybrid(q, embedder, conn, TOP_K) for q in answerable]
    else:
        print(f"unknown mode: {args.mode!r}")
        sys.exit(1)

    metrics = evaluate(answerable, retrieved, TOP_K)

    config = RunConfig(
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        embedding_model=args.model,
        top_k=TOP_K,
        retrieval_mode=args.mode,
    )
    log_run(config, metrics, args.experiment)

    print(f"scored {len(answerable)} answerable questions (mode={args.mode})")
    for name, value in metrics.items():
        print(f"  {name}: {value:.3f}")

    if args.gate:
        check_gate(args.mode, metrics)


if __name__ == "__main__":
    main()
