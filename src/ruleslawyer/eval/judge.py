"""Generation evals: LLM-as-judge scoring of answer faithfulness.

Functional core (the pure scorers) / imperative shell (the Judge's LLM call).
"""

import json
from pathlib import Path

import anthropic

from ruleslawyer.generation.llm import Settings, _format_context
from ruleslawyer.retrieval.search import SearchResult

# pinned snapshot, not the floating alias — the judge is a fixed measuring stick
JUDGE_MODEL = "claude-haiku-4-5-20251001"

_JUDGE_PROMPT = (
    Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "judge_faithfulness_v1.md"
).read_text()


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

        claims: list[dict[str, str | bool]] = json.loads(raw)["claims"]
        return claims


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
