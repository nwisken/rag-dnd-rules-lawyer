"""Retrieval metrics for the golden set, as pure functions over heading paths."""


def is_grounded_by(heading_path: str, grounding: str) -> bool:
    """Tests whether a heading path sits at or below a grounding path in the tree.

    Args:
        heading_path: a chunk's full heading path, e.g "Cover > Half Cover".
        grounding: a grounding path from the golden set, e.g "Cover".

    Returns:
        True if heading_path is the grounding section or one nested under it.
    """
    return heading_path == grounding or heading_path.startswith(grounding + " > ")
