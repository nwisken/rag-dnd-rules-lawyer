"""LLM client wrapping the Anthropic SDK for answer generation."""

import anthropic

# TODO: refine prompt
SYSTEM_PROMPT = "You are a expert Dungeons and Dragons Dungeon master"


class LLMClient:
    """Wraps the Anthropic Messages API behind a single generate call.

    Construction creates the client (reads ANTHROPIC_API_KEY from env).
    Model and max_tokens are per-instance config; query and edition vary per call.

    Args:
        model: Anthropic model ID to use.
        max_tokens: maximum tokens in the generated response.
    """

    def __init__(self, model: str = "claude-haiku-4-5", max_tokens: int = 1024) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic()

    def generate(self, query: str, edition: str | None = None) -> str:
        """Send a query to the LLM and return the generated text.

        Args:
            query: the user's rules question.
            edition: optional edition tag appended to the query.

        Returns:
            the concatenated text from all response content blocks.
        """
        message = query
        if edition:
            message += f" {edition}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )

        answer = ""
        for block in response.content:
            if block.type == "text":
                answer += block.text

        return answer
