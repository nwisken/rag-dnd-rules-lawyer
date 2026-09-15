"""Scores generation quality over the golden set and logs one MLflow run.

Faithfulness and answer relevance are scored over the answerable questions; refusal
accuracy over the deliberately unanswerable ones. Each score is an LLM-as-judge call
(see ruleslawyer.eval.judge), so a full run makes many API calls — expect a few minutes.

Usage:
    uv run python scripts/run_generation_eval.py
    uv run python scripts/run_generation_eval.py --experiment generation-baseline
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import psycopg

from ruleslawyer.eval.golden_set import GoldenQuestion, load_golden_set
from ruleslawyer.eval.judge import Judge, faithfulness_score, refusal_accuracy, relevance_score
from ruleslawyer.eval.tracking import GenerationRunConfig, log_generation_run
from ruleslawyer.generation.llm import LLMClient
from ruleslawyer.ingest.embed import Embedder
from ruleslawyer.ingest.load import connect
from ruleslawyer.retrieval.search import SearchResult, search_vectors

GOLDEN_SET_PATH = Path("evals/golden_set.jsonl")
BASELINES_PATH = Path("evals/baselines.json")
DEFAULT_EXPERIMENT = "generation-baseline"
ANSWER_PROMPT = "answer_v2"
TOP_K = 5


def check_gate(metrics: dict[str, float]) -> None:
    """Fails the process if faithfulness dropped past max(floor, baseline - tolerance).

    Args:
        metrics: the just-computed generation metrics.
    """
    baselines = json.loads(BASELINES_PATH.read_text())
    gen = baselines["generation"]
    floor = max(gen["faithfulness_floor"], gen["faithfulness"] - baselines["tolerance"])
    actual = metrics["faithfulness"]
    if actual < floor:
        print(f"GATE FAIL: faithfulness {actual:.3f} < floor {floor:.3f}")
        sys.exit(1)
    print(f"GATE PASS: faithfulness {actual:.3f} >= floor {floor:.3f}")


def mean(values: list[float]) -> float:
    """Averages scores, 0.0 for an empty list rather than raising."""
    return sum(values) / len(values) if values else 0.0


def answer_for(
    question: GoldenQuestion,
    embedder: Embedder,
    conn: psycopg.Connection[Any],
    llm: LLMClient,
    top_k: int,
) -> tuple[list[SearchResult], str]:
    """Retrieves and generates one answer, exactly as the live app would.

    Args:
        question: the golden question to answer.
        embedder: the process-wide Embedder.
        conn: open psycopg connection.
        llm: the answer generator.
        top_k: how many chunks to retrieve.

    Returns:
        The retrieved chunks and the generated answer text.
    """
    results = search_vectors(question.question, embedder, conn, question.edition, top_k)
    answer = llm.generate(query=question.question, results=results).answer
    return results, answer


def main() -> None:
    """Scores generation over the golden set and logs it to MLflow."""
    args = parse_args()
    golden = load_golden_set(GOLDEN_SET_PATH)
    answerable = [q for q in golden if q.answerable]
    unanswerable = [q for q in golden if not q.answerable]

    conn = connect()
    embedder = Embedder()
    llm = LLMClient()
    judge = Judge()

    faithfulness_scores: list[float] = []
    relevance_scores: list[float] = []
    for q in answerable:
        results, answer = answer_for(q, embedder, conn, llm, TOP_K)
        claims = judge.faithfulness_claims(results, answer)
        # a wrongly-refused answerable question yields no claims; it still scores
        # relevance "none" below, so over-refusal is penalised there, not here
        if claims:
            faithfulness_scores.append(faithfulness_score(claims))
        relevance_scores.append(relevance_score(judge.relevance_label(q.question, answer)))

    refusals: list[bool] = []
    for q in unanswerable:
        _results, answer = answer_for(q, embedder, conn, llm, TOP_K)
        refusals.append(judge.is_refusal(q.question, answer))

    metrics = {
        "faithfulness": mean(faithfulness_scores),
        "answer_relevance": mean(relevance_scores),
        "refusal_accuracy": refusal_accuracy(refusals),
    }

    config = GenerationRunConfig(
        answer_model=llm.model,
        answer_prompt=ANSWER_PROMPT,
        judge_model=judge.model,
        top_k=TOP_K,
    )
    log_generation_run(config, metrics, args.experiment)

    print(f"scored {len(answerable)} answerable, {len(unanswerable)} unanswerable questions")
    for name, value in metrics.items():
        print(f"  {name}: {value:.3f}")

    if args.gate:
        check_gate(metrics)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score generation quality and log to MLflow.")
    parser.add_argument(
        "--experiment",
        type=str,
        default=DEFAULT_EXPERIMENT,
        help=f"MLflow experiment name (default: {DEFAULT_EXPERIMENT})",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="exit non-zero if faithfulness regressed past max(floor, baseline - tolerance)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
