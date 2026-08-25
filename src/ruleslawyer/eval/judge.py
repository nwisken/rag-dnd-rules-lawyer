"""Generation evals: LLM-as-judge scoring of answer faithfulness and refusal behaviour.

Functional core (the pure scorers) / imperative shell (the Judge's LLM call).
"""

import json
from pathlib import Path

import anthropic

from ruleslawyer.generation.llm import Settings, _format_context
from ruleslawyer.retrieval.search import SearchResult

# pinned snapshot, not the floating alias — the judge is a fixed measuring stick
JUDGE_MODEL = "claude-haiku-4-5-20251001"

_PROMPTS = Path(__file__).resolve().parent.parent.parent.parent / "prompts"
_JUDGE_PROMPT = (_PROMPTS / "judge_faithfulness_v1.md").read_text()
_REFUSAL_PROMPT = (_PROMPTS / "judge_refusal_v1.md").read_text()
_RELEVANCE_PROMPT = (_PROMPTS / "judge_relevance_v1.md").read_text()


def _strip_to_json(raw: str) -> str:
    """Extract the JSON object from an LLM reply, tolerating code fences or stray prose.

    Args:
        raw: the model's reply, possibly wrapped in ```json fences or surrounding text.

    Returns:
        The substring from the first "{" to the last "}", ready for json.loads.
    """
    return raw[raw.index("{") : raw.rindex("}") + 1]


class Judge:
    """LLM-as-judge for generation evals. The model is pinned for reproducible scores."""

    def __init__(self, model: str = JUDGE_MODEL, max_tokens: int = 1024) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=Settings().anthropic_api_key)

    def faithfulness_claims(
        self, results: list[SearchResult], answer: str
    ) -> list[dict[str, str | bool]]:
        """Judge one answer: decompose into claims, mark each supported by the sources.

        Args:
            results: the same retrieved chunks the answer was generated from.
            answer: the generated answer to grade.

        Returns:
            the judge's parsed "claims" list, ready for faithfulness_score.
        """

        context = _format_context(results)
        prompt = _JUDGE_PROMPT.format(context=context, answer=answer)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = ""
        for block in response.content:
            if block.type == "text":
                raw += block.text

        claims: list[dict[str, str | bool]] = json.loads(_strip_to_json(raw))["claims"]
        return claims

    def is_refusal(self, question: str, answer: str) -> bool:
        """Classify whether an answer declined rather than attempting a rules answer.

        Args:
            question: the user's question.
            answer: the generated answer to classify.

        Returns:
            True if the answer refused, False if it attempted an answer (even a wrong one).
        """
        prompt = _REFUSAL_PROMPT.format(question=question, answer=answer)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = ""
        for block in response.content:
            if block.type == "text":
                raw += block.text

        refused: bool = json.loads(_strip_to_json(raw))["refused"]
        return refused

    def relevance_label(self, question: str, answer: str) -> str:
        """Classify how well an answer addresses the question, as a rubric label.

        Args:
            question: the user's question.
            answer: the generated answer to classify.

        Returns:
            the rubric label "full", "partial", or "none".
        """
        prompt = _RELEVANCE_PROMPT.format(question=question, answer=answer)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = ""
        for block in response.content:
            if block.type == "text":
                raw += block.text

        label: str = json.loads(_strip_to_json(raw))["relevance"]
        return label


def faithfulness_score(claims: list[dict[str, str | bool]]) -> float:
    """Fraction of the judge's claims that were marked supported.

    Args:
        claims: the judge's parsed claims, each a dict with a "supported" bool.

    Returns:
        supported claims / total claims, 0.0 to 1.0.

    Raises:
        ValueError: if claims is empty, i.e a refusal scored by the refusal metric instead.
    """

    if not claims:
        raise ValueError(
            "faithfulness_score needs at least one claim; refusals are scored elsewhere"
        )

    return sum(True for claim in claims if claim["supported"]) / len(claims)


def refusal_accuracy(refusals: list[bool]) -> float:
    """Fraction of unanswerable questions the app correctly refused.

    Args:
        refusals: one bool per unanswerable question — True if the app declined.

    Returns:
        correct refusals / total, 0.0 to 1.0.

    Raises:
        ValueError: if refusals is empty, i.e no unanswerable questions were scored.
    """

    if not refusals:
        raise ValueError("refusal_accuracy needs at least one unanswerable question")

    return sum(refusals) / len(refusals)


_RELEVANCE_SCORES = {"full": 1.0, "partial": 0.5, "none": 0.0}


def relevance_score(label: str) -> float:
    """Map a relevance rubric label to a number.

    Args:
        label: the judge's rubric label — "full", "partial", or "none".

    Returns:
        1.0 for "full", 0.5 for "partial", 0.0 for "none".

    Raises:
        ValueError: if label is not one of the three known rubric labels.
    """
    if label not in _RELEVANCE_SCORES:
        raise ValueError(f"unknown relevance label: {label!r}")

    return _RELEVANCE_SCORES[label]
