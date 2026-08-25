"""Tests the MLflow param conversion"""

from ruleslawyer.eval.tracking import (
    GenerationRunConfig,
    RunConfig,
    config_to_params,
    generation_config_to_params,
)

CONFIG = RunConfig(
    chunk_size=400,
    overlap=50,
    embedding_model="BAAI/bge-small-en-v1.5",
    top_k=5,
    retrieval_mode="vector",
)

GEN_CONFIG = GenerationRunConfig(
    answer_model="claude-haiku-4-5",
    answer_prompt="answer_v2",
    judge_model="claude-haiku-4-5-20251001",
    top_k=5,
)


def test_params_match_the_config() -> None:
    """checks every setting arrives under its own key, numbers stringified"""
    assert config_to_params(CONFIG, "a3f9c1d") == {
        "chunk_size": "400",
        "overlap": "50",
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "top_k": "5",
        "retrieval_mode": "vector",
        "git_sha": "a3f9c1d",
    }


def test_sha_is_a_value_not_a_key() -> None:
    """guards the bug where the sha was used as its own key"""
    params = config_to_params(CONFIG, "a3f9c1d")
    assert "a3f9c1d" not in params


def test_generation_params_match_the_config() -> None:
    """checks every generation setting arrives under its own key, numbers stringified"""
    assert generation_config_to_params(GEN_CONFIG, "a3f9c1d") == {
        "answer_model": "claude-haiku-4-5",
        "answer_prompt": "answer_v2",
        "judge_model": "claude-haiku-4-5-20251001",
        "top_k": "5",
        "git_sha": "a3f9c1d",
    }
