"""LLM client wrapping the Anthropic SDK for answer generation."""
from __future__ import annotations

from pathlib import Path

import anthropic

from ruleslawyer.retrieval.search import SearchResult

_PROMPT_TEMPLATE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "prompts"
    / "answer_v1.md"
).read_text()


def _format_context(results: list[SearchResult]) -> str:
    """Format retrieved chunks into numbered source blocks for the prompt."""
    if not results:
        return "No sources available."
    blocks: list[str] = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"[{i}]\n"
            f"Edition: {r.edition}\n"
            f"Section: {r.heading_path}\n"
            f"Content: {r.content}"
        )
    return "\n\n".join(blocks)


class LLMClient:
    """Wraps the Anthropic Messages API behind a single generate call.

    Construction creates the client (reads ANTHROPIC_API_KEY from env).
    Model and max_tokens are per-instance config; query and results vary per call.

    Args:
        model: Anthropic model ID to use.
        max_tokens: maximum tokens in the generated response.
    """

    def __init__(self, model: str = "claude-haiku-4-5", max_tokens: int = 1024) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic()

    def generate(self, query: str, results: list[SearchResult]) -> str:
        """Send a query with retrieved context to the LLM and return the answer.

        Args:
            query: the user's rules question.
            results: retrieved chunks from search.

        Returns:
            the concatenated text from all response content blocks.
        """
        system_prompt = _PROMPT_TEMPLATE.format(context=_format_context(results))

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": query}],
        )

        answer = ""
        for block in response.content:
            if block.type == "text":
                answer += block.text

        return answer
