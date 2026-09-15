"""LLM client wrapping the Anthropic SDK for answer generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import anthropic
from pydantic_settings import BaseSettings, SettingsConfigDict

from ruleslawyer.retrieval.search import SearchResult


class Settings(BaseSettings):
    """LLM credentials, read from the environment (or .env for local dev)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str


# prompts live at repo root in dev; the served image copies them and sets RULESLAWYER_PROMPTS_DIR
_PROMPTS_DIR = Path(
    os.environ.get("RULESLAWYER_PROMPTS_DIR")
    or Path(__file__).resolve().parents[3] / "prompts"
)
_PROMPT_TEMPLATE = (_PROMPTS_DIR / "answer_v2.md").read_text()


def _format_context(results: list[SearchResult]) -> str:
    """Format retrieved chunks into numbered source blocks for the prompt."""
    if not results:
        return "No sources available."
    blocks: list[str] = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"[{i}]\nEdition: {r.edition}\nSection: {r.heading_path}\nContent: {r.content}"
        )
    return "\n\n".join(blocks)


@dataclass(frozen=True)
class GenerationResult:
    """A generated answer plus the token usage the query log records."""

    answer: str
    prompt_tokens: int
    completion_tokens: int


class LLMClient:
    """Wraps the Anthropic Messages API behind a single generate call.

    Construction creates the client, reading ANTHROPIC_API_KEY via Settings
    (environment first, then .env) and passing it to the SDK explicitly —
    the SDK only checks os.environ, which .env never populates.
    Model and max_tokens are per-instance config; query and results vary per call.

    Args:
        model: Anthropic model ID to use.
        max_tokens: maximum tokens in the generated response.
    """

    def __init__(self, model: str = "claude-haiku-4-5", max_tokens: int = 1024) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=Settings().anthropic_api_key)

    def generate(self, query: str, results: list[SearchResult]) -> GenerationResult:
        """Send a query with retrieved context to the LLM and return the answer + usage.

        Args:
            query: the user's rules question.
            results: retrieved chunks from search.

        Returns:
            the concatenated answer text and the request's token usage.
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

        return GenerationResult(
            answer=answer,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )
