"""Pydantic request/response models for the API.

FastAPI auto-validates incoming JSON against these
and auto-serializes them to JSON in the response.
"""

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    edition: str | None = None


class Source(BaseModel):
    edition: str
    heading_path: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


class FeedbackRequest(BaseModel):
    question: str
    answer: str
    edition: str | None = None
    verdict: str
    retrieved_paths: list[str] = []
