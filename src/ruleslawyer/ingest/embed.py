"""Embed chunk texts and queries with a sentence-transformers model."""

from ruleslawyer.ingest.types import Chunk

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def embedding_input(chunk: Chunk) -> str:
    """Builds the string that actually gets embedded for a chunk.

    Prepends the heading path (contextual enrichment) so the vector carries
    context the bare content lacks. The stored content stays clean; only the
    embedding sees this enriched form.

    Args:
        chunk: the chunk to build the embedding input for.

    Returns:
        "<path joined with ' > '>\\n\\n<content>", or bare content when the
        chunk has an empty heading path.
    """
    if not chunk.heading_path:
        return chunk.content
    return " > ".join(chunk.heading_path) + "\n\n" + chunk.content


class Embedder:
    """Wraps one embedding model: construction is the single expensive step.

    Loading downloads the model on first ever use (~130 MB) and takes seconds;
    build one Embedder per process and pass it around.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        """Loads the model.

        Args:
            model_name: sentence-transformers / Hugging Face model id.
        """
        # imported here, not at module top: importing sentence_transformers pulls
        # in torch (~20 s), which would tax every test run that merely imports
        # this module without ever building an Embedder
        from sentence_transformers import SentenceTransformer

        self._model: SentenceTransformer = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        """Vector size this model produces; must match the DB's vector(N) column."""
        dimension: int | None = self._model.get_embedding_dimension()
        if dimension is None:  # only for un-configured models; ours always knows
            raise ValueError("model does not report an embedding dimension")
        return dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embeds a batch of texts into normalized vectors.

        Args:
            texts: the texts to embed (enriched chunk inputs, or a raw query).

        Returns:
            One vector per input text, in order, each of length `dimension`
            and unit-normalized so cosine similarity and dot product agree.
        """
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return [embedding.tolist() for embedding in embeddings]

    def count_tokens(self, text: str) -> int:
        """Counts tokens with this model's own tokenizer (a TokenCounter).

        Chunk budgets exist to respect THIS model's input limit, so production
        chunking must measure with the same tokenizer the model uses.

        Args:
            text: the text to measure.

        Returns:
            The token count, including special tokens ([CLS]/[SEP]), since they
            occupy the same input budget.
        """
        tokens: list[int] = self._model.tokenizer.encode(text)
        return len(tokens)
