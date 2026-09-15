"""Creates the FastAPI app, stands up shared resources and exposes /health, /ask, /feedback"""

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from psycopg import Connection
from psycopg import Error as PsycopgError

from ruleslawyer.api.models import AskRequest, AskResponse, FeedbackRequest, Source
from ruleslawyer.generation.llm import GenerationResult, LLMClient
from ruleslawyer.ingest.embed import Embedder
from ruleslawyer.ingest.load import connect
from ruleslawyer.retrieval.search import SearchResult, search_vectors

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Everything BEFORE yield runs at startup
    embedder = Embedder()
    conn = connect()
    llm_client = LLMClient()
    app.state.embedder = embedder
    app.state.conn = conn
    app.state.llm_client = llm_client
    yield
    # Everything AFTER yield runs at shutdown
    conn.close()


app = FastAPI(lifespan=lifespan)

# send request/latency/error telemetry to App Insights when configured (prod); a no-op otherwise
if _appinsights := os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    configure_azure_monitor(connection_string=_appinsights)
    FastAPIInstrumentor.instrument_app(app)


# liveness/readiness probe: 200 only after lifespan loaded the model and opened the DB
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# best-effort: a logging failure must never fail the user's answer, so it swallows and rolls back
def _log_query(
    conn: Connection[Any],
    body: AskRequest,
    results: list[SearchResult],
    gen: GenerationResult,
    latency_ms: int,
) -> None:
    insert_sql = (
        "INSERT INTO query_log (question, edition_filter, retrieved_paths, scores,"
        " answer_chars, prompt_tokens, completion_tokens, latency_ms)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    try:
        conn.execute(
            insert_sql,
            (
                body.question,
                body.edition,
                [r.heading_path for r in results],
                [r.score for r in results],
                len(gen.answer),
                gen.prompt_tokens,
                gen.completion_tokens,
                latency_ms,
            ),
        )
        conn.commit()
    except PsycopgError:
        conn.rollback()
        logger.warning("failed to write query_log row", exc_info=True)


# FastAPI injects two parameters automatically:
#   body: AskRequest  — parsed from the POST JSON body
#   request: Request   — the raw HTTP request, gives access to app.state
@app.post("/ask")
def ask(body: AskRequest, request: Request) -> AskResponse:
    start = time.perf_counter()
    results = search_vectors(
        query=body.question,
        embedder=request.app.state.embedder,
        conn=request.app.state.conn,
        edition=body.edition,
    )

    gen = request.app.state.llm_client.generate(
        query=body.question,
        results=results,
    )

    sources = [
        Source(
            edition=r.edition,
            heading_path=r.heading_path,
            score=r.score,
        )
        for r in results
    ]

    # end-to-end latency: what the user actually waits for (retrieval + generation)
    latency_ms = int((time.perf_counter() - start) * 1000)
    _log_query(request.app.state.conn, body, results, gen, latency_ms)

    return AskResponse(answer=gen.answer, sources=sources)


@app.post("/feedback")
def feedback(body: FeedbackRequest, request: Request) -> dict[str, str]:
    # parameterized insert: values travel in a separate channel from the SQL text
    insert_sql = (
        "INSERT INTO feedback (question, answer, edition, verdict, retrieved_paths)"
        " VALUES (%s, %s, %s, %s, %s)"
    )
    conn = request.app.state.conn
    try:
        conn.execute(
            insert_sql,
            (body.question, body.answer, body.edition, body.verdict, body.retrieved_paths),
        )
        conn.commit()
    except PsycopgError as err:
        # roll back so a rejected insert can't poison the shared connection
        conn.rollback()
        raise HTTPException(status_code=400, detail="Could not record feedback") from err
    return {"status": "recorded"}
