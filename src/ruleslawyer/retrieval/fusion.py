"""Module to fuse Reciprocal Rank searches using vectors and keywords together. """


def reciprocal_rank_fusion(
    vector_paths: list[str],
    text_paths: list[str],
    k: int = 60,
) -> list[str]:
    """Fuses two ranked lists into one using Reciprocal Rank Fusion.

    Higher k flattens the rank gaps; lower k lets the top positions dominate.
    60 is the paper default and rarely needs changing.
    Uses ranks not scores, so no normalization needed between searchers.

    Args:
        vector_paths: heading paths from vector search, best match first.
        text_paths: heading paths from full-text search, best match first.
        k: smoothing constant that controls how much rank differences matter.

    Returns:
        Merged heading paths sorted by combined RRF score, best first.
    """
    scores: dict[str, float] = {}
    for rank, path in enumerate(vector_paths, start=1):
        scores[path] = scores.get(path, 0.0) + 1 / (k + rank)
    for rank, path in enumerate(text_paths, start=1):
        scores[path] = scores.get(path, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda p: scores[p], reverse=True)