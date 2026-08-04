"""Tests the MLflow param conversion"""

from ruleslawyer.eval.tracking import RunConfig, config_to_params

CONFIG = RunConfig(
    chunk_size=400,
    overlap=50,
    embedding_model="BAAI/bge-small-en-v1.5",
    top_k=5,
    retrieval_mode="vector",
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
