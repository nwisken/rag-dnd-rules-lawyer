"""Creates the FastAPI app, stands up shared resources and exposes a POST /ask endpoint"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ruleslawyer.generation.llm import LLMClient
from ruleslawyer.ingest.embed import Embedder
from ruleslawyer.ingest.load import connect


@asynccontextmanager
async def lifespan(app: FastAPI):
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