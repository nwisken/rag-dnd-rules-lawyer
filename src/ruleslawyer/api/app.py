"""Creates the FastAPI app, stands up shared resources and exposes a POST /ask endpoint"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from psycopg import Error as PsycopgError

from ruleslawyer.api.models import AskRequest, AskResponse, FeedbackRequest, Source
from ruleslawyer.generation.llm import LLMClient
from ruleslawyer.ingest.embed import Embedder
from ruleslawyer.ingest.load import connect
from ruleslawyer.retrieval.search import search_vectors


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


# FastAPI injects two parameters automatically:
#   body: AskRequest  — parsed from the POST JSON body
#   request: Request   — the raw HTTP request, gives access to app.state
@app.post("/ask")
def ask(body: AskRequest, request: Request) -> AskResponse:
    results = search_vectors(
        query=body.question,
        embedder=request.app.state.embedder,
        conn=request.app.state.conn,
        edition=body.edition,
    )

    answer = request.app.state.llm_client.generate(
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

    return AskResponse(answer=answer, sources=sources)


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
