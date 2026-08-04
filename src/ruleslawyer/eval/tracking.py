"""Tracks changes and results from experiments to improve the RAG retrieval."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunConfig:
    """The retrieval settings that define one experiment."""

    chunk_size: int
    overlap: int
    embedding_model: str
    top_k: int
    retrieval_mode: str


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
