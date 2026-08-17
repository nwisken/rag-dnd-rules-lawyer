"""Creates the FastAPI app, stands up shared resources and exposes a POST /ask endpoint"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from ruleslawyer.api.models import AskRequest, AskResponse, Source
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
