"""Retrieval metrics for the golden set, as pure functions over heading paths."""

from collections.abc import Sequence


def is_grounded_by(heading_path: str, grounding: str) -> bool:
    """Tests whether a heading path sits at or below a grounding path in the tree.

    Args:
        heading_path: a chunk's full heading path, e.g "Cover > Half Cover".
        grounding: a grounding path from the golden set, e.g "Cover".

    Returns:
        True if heading_path is the grounding section or one nested under it.
    """
    return heading_path == grounding or heading_path.startswith(grounding + " > ")


def recall_at_k(retrieved_paths: Sequence[str], grounding: Sequence[str], k: int) -> float:
    """Scores the fraction of a question's grounding sections found in the top k.

    Args:
        retrieved_paths: heading paths of the retrieved chunks, best match first.
        grounding: the grounding paths for one golden-set question.
        k: how many of the retrieved paths to score.

    Returns:
        Grounding sections found divided by grounding sections total, 0.0 to 1.0.

    Raises:
        ValueError: if grounding is empty, i.e an unanswerable question slipped through.
    """
    if not grounding:
        raise ValueError("recall_at_k needs at least one grounding path")

    top_k = retrieved_paths[:k]

    found = 0
    for g in grounding:
        # one grounding section counts once however many chunks land under it
        if any(is_grounded_by(path, g) for path in top_k):
            found += 1

    return found / len(grounding)
