"""Tracks changes and results from experiments to improve the RAG retrieval."""


import subprocess
from dataclasses import dataclass

import mlflow

# local db file, not a server
mlflow.set_tracking_uri("sqlite:///mlflow.db")


@dataclass(frozen=True, slots=True)
class RunConfig:
    """The retrieval settings that define one experiment."""

    chunk_size: int
    overlap: int
    embedding_model: str
    top_k: int
    retrieval_mode: str


@dataclass(frozen=True, slots=True)
class GenerationRunConfig:
    """The settings that define one generation-eval run.

    The judge prompts are versioned files in prompts/, so the git SHA (logged with
    every run) already pins their exact text — no need to log them as params.
    """

    answer_model: str
    answer_prompt: str
    judge_model: str
    top_k: int


def config_to_params(config: RunConfig, git_sha: str) -> dict[str, str]:
    """Converts a RunConfig object to a dict of parameters.

    Args:
        config: The retrieval settings for this run.
        git_sha: The commit the run was evaluated at.

    Returns:
        The settings as strings, keyed by param name, ready for MLflow.
    """
    return {
        "chunk_size": str(config.chunk_size),
        "overlap": str(config.overlap),
        "embedding_model": config.embedding_model,
        "top_k": str(config.top_k),
        "retrieval_mode": config.retrieval_mode,
        "git_sha": git_sha,
    }


def generation_config_to_params(config: GenerationRunConfig, git_sha: str) -> dict[str, str]:
    """Converts a GenerationRunConfig to a dict of MLflow parameters.

    Args:
        config: the generation-eval settings for this run.
        git_sha: the commit the run was evaluated at.

    Returns:
        The settings as strings, keyed by param name, ready for MLflow.
    """
    return {
        "answer_model": config.answer_model,
        "answer_prompt": config.answer_prompt,
        "judge_model": config.judge_model,
        "top_k": str(config.top_k),
        "git_sha": git_sha,
    }


def get_git_sha() -> str:
    """Gets the git commit sha for this run."""
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()


def log_run(config: RunConfig, metrics: dict[str, float], experiment: str) -> None:
    """Logs metrics to MLflow.

    Args:
        config: The retrieval settings for this run.
        metrics: The metrics to log.
        experiment: Name of the experiment to log to
    """

    mlflow.set_experiment(experiment_name=experiment)
    with mlflow.start_run():
        mlflow.log_params(config_to_params(config, get_git_sha()))
        mlflow.log_metrics(metrics)


def log_generation_run(
    config: GenerationRunConfig, metrics: dict[str, float], experiment: str
) -> None:
    """Logs one generation-eval run to MLflow.

    Args:
        config: the generation-eval settings for this run.
        metrics: the faithfulness / relevance / refusal scores to log.
        experiment: name of the experiment to log to.
    """
    mlflow.set_experiment(experiment_name=experiment)
    with mlflow.start_run():
        mlflow.log_params(generation_config_to_params(config, get_git_sha()))
        mlflow.log_metrics(metrics)


