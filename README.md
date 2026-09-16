# Rules Lawyer — a D&D 5e RAG Assistant

[![CI](https://github.com/nwisken/rag-dnd-rules-lawyer/actions/workflows/ci.yml/badge.svg)](https://github.com/nwisken/rag-dnd-rules-lawyer/actions/workflows/ci.yml)

Answers Dungeons & Dragons 5th Edition rules questions with cited sources, aware of
the difference between the 2014 rules (SRD 5.1) and the revised 2024 rules (SRD 5.2).

## Why this isn't another RAG tutorial

Most RAG demos are a LangChain tutorial with a different PDF. This project differs by:

1. **Hybrid retrieval** (pgvector cosine + Postgres full-text, fused with RRF) —
   evaluated against pure vector and pure keyword baselines, with the finding that
   vector search is near-ceiling on this corpus. The experiment is the point: we
   prove the claim with numbers rather than assuming hybrid always wins.
2. **Version-aware answers** via metadata filtering across two rule editions.
3. **Evaluated, not vibes-checked**: a golden Q&A set, retrieval + generation metrics
   tracked in MLflow, and evals gating CI.
4. **Actually deployed**: containerised, CI/CD to Azure Container Apps, monitored.

## Architecture

```
                         ┌─────────────────────────────────┐
 user ─▶ Streamlit UI ──▶│ FastAPI backend                 │
        (edition toggle, │  /ask   /health   /feedback     │
         cited answer,   │                                 │
         chunks panel,   │  Retriever                      │
         👍/👎 feedback)  │   ├─ vector search (pgvector)   │
                         │   ├─ full-text search (tsvector)│
                         │   └─ RRF fusion + edition filter│
                         │  Generator (LLM, cited answer)  │
                         └───────┬─────────────────────────┘
                                 │
             Postgres 16 + pgvector  (chunks, embeddings, metadata,
                                 │    feedback, query_log)
                                 │
   MLflow (experiments)   GitHub Actions (CI: ruff + mypy + pytest +
                                 │           retrieval-eval gate → CD)
   App Insights (traces)   Azure Container Apps (scale-to-zero runtime)
```

The whole app runs locally with one `docker compose up` (Postgres + pgvector, API,
UI, MLflow); the same images deploy to Azure Container Apps via GitHub Actions. See
[`infra/`](infra/) for the Bicep and the deploy runbook.

The API and UI ship as separate images with split dependency groups: the API image is
2.25 GB (CPU-only torch — pinning the `pytorch-cpu` wheel index cuts ~6.5 GB of unused
CUDA the default PyPI wheel would drag in), and the UI image is 792 MB (Streamlit alone,
no torch — it carries pandas/pyarrow/numpy).

## Example questions

Drawn from the golden eval set (`evals/golden_set.jsonl`) — each one exercises a
different part of the pipeline:

- *"When do I provoke an opportunity attack?"* — **hybrid retrieval.** "Opportunity
  attack" is a fixed piece of rules jargon, exactly the query shape where keyword
  search beats embeddings and pure vector search drifts toward generically
  combat-flavoured text.
- *"Does Sneak Attack work with a thrown dagger?"* — **multi-section retrieval.** The
  answer needs both the Sneak Attack rule and the definition of the *finesse* weapon
  property; retrieving only one of them produces a refusal rather than an answer.
- *"What's the save DC for a Fireball cast by a 5th-level wizard with 16 Intelligence?"*
  — **multi-hop.** Three separate sections: the save DC formula, the wizard's
  spellcasting ability, and the proficiency bonus for the character's level.
- *"Compare grappling in the 2014 and 2024 rules."* — **edition-aware retrieval** via
  metadata filtering. (Pending SRD 5.2 ingestion.)
- *"How does the Lucky feat work?"* — **honest refusal.** The SRD has no Lucky feat,
  but it does describe a halfling racial trait of the same name. Answering with the
  trait is a wrong answer, not a refusal.

## Status

Phase 4 (ship it) in progress: containerised (multi-stage, non-root, CPU-only torch),
GitHub Actions CI with an eval gate, CD to Azure Container Apps over OIDC, and per-query
monitoring. Phase 3 delivered citation-forced prompting, honest refusal on non-SRD
questions, generation evals, and a thumbs up/down feedback endpoint.

**Live demo:** _pending first Azure deploy_ — public URL lands here once it is up.

### Retrieval baselines (top-5, 20 answerable golden questions)

| Mode | recall@5 | MRR |
|---|---|---|
| vector (bge-small-en-v1.5) | 0.892 | 0.821 |
| full-text (ts_rank_cd) | 0.300 | 0.260 |
| hybrid (RRF fusion) | 0.892 | 0.789 |

Hybrid recall matches vector; MRR is slightly worse. Vector search is near-ceiling on
this corpus, and keyword search is weak enough (AND-joining via `plainto_tsquery` means
multi-word queries often return zero results) that fusing it in dilutes the top
rankings rather than improving them.

### Chunking experiments (2 chunk sizes x 2 embedding models x 2 retrieval modes)

| Chunk size | Model | Mode | recall@5 | MRR |
|---|---|---|---|---|
| 400 | bge-small-en-v1.5 | vector | 0.892 | 0.821 |
| 400 | bge-small-en-v1.5 | hybrid | 0.892 | 0.789 |
| 200 | bge-small-en-v1.5 | vector | 0.825 | 0.800 |
| 200 | bge-small-en-v1.5 | hybrid | 0.825 | 0.692 |
| 400 | all-MiniLM-L6-v2 | vector | 0.867 | 0.850 |
| 400 | all-MiniLM-L6-v2 | hybrid | 0.867 | 0.817 |
| 200 | all-MiniLM-L6-v2 | vector | **0.892** | **0.883** |
| 200 | all-MiniLM-L6-v2 | hybrid | 0.892 | 0.821 |

Key finding: 200-token chunks with all-MiniLM-L6-v2 tied the best recall and posted the
highest MRR (0.883). MiniLM's 256-token context window means 400-token chunks are
silently truncated, losing content from the embedding. Smaller chunks that fit within
the window avoid this. Conversely, bge-small-en-v1.5 (512-token window) benefits from
the richer context in 400-token chunks — halving the chunk size drops its recall from
0.892 to 0.825.

### Generation quality (LLM-as-judge, 25 golden questions)

| Metric | Score |
|---|---|
| Faithfulness | 0.914 |
| Answer relevance | 0.925 |
| Refusal accuracy | 1.000 |

Measured by a hand-rolled LLM-as-judge (not RAGAS) over the golden set — 20 answerable
questions for faithfulness and answer relevance, 5 non-SRD questions for refusal
accuracy. **Faithfulness** = share of answer claims inferable from the retrieved chunks
alone; **answer relevance** = a full/partial/none rubric mapped to 1/0.5/0; **refusal
accuracy** = correct honest-refusal rate on non-SRD questions, where handing back a
similarly named rule counts as a failed attempt, not a refusal. The judge is pinned to a
model snapshot (`claude-haiku-4-5-20251001`) so the measuring stick can't drift between
runs. Faithfulness doubles as a retrieval signal: a low score points at missing context,
not a hallucinating model.

## Monitoring

Two layers of observability, deliberately separate:

**Application-level — the `query_log` table.** Every `/ask` writes one row: the
`question`, the `edition_filter`, the `retrieved_paths` (heading paths of the retrieved
chunks in rank order) with their `scores`, `answer_chars`, `prompt_tokens` /
`completion_tokens` from the LLM response, and `latency_ms` for the full
retrieve-and-generate turn. Paths are logged rather than chunk UUIDs so the log stays
joinable across re-ingests (the same label-invariance rule the golden set follows). A
`feedback_id` FK is reserved to link a row to its 👍/👎 vote. Logging is **best-effort**:
a failed write rolls back and warns but never breaks the answer the user is waiting for.
This table is the raw material for drift and quality review — which questions retrieve
nothing, where latency or token cost spikes, and (via feedback) which answers users
reject.

**Platform-level — Azure Application Insights.** The API auto-instruments FastAPI with
OpenTelemetry for request latency, error rates, and traces. It is guarded: instrumentation
activates only when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set (injected by Bicep in
Azure), so local dev and tests never touch the exporter.

## Local setup

One command brings up the whole stack — Postgres + pgvector, the FastAPI backend, the
Streamlit UI, and MLflow:

```sh
cp .env.example .env      # then set ANTHROPIC_API_KEY (the api service won't start without it)
docker compose up -d      # db + api + ui + mlflow, all on the compose network
```

- **UI** → http://localhost:8501  ·  **API docs** → http://localhost:8000/docs  ·
  **MLflow** → http://localhost:5000

The database starts empty. Populate it once (fetches the SHA-pinned SRD corpus, then
chunks, embeds, and loads it) using the host Python environment:

```sh
uv sync                              # Python 3.12 env
uv run python scripts/fetch_corpus.py
uv run python scripts/ingest.py      # ~2,585 chunks into pgvector
```

The `pgdata` volume persists across restarts, so ingest is a one-time step per fresh
volume. (`make` isn't required — run the underlying `uv run` commands directly.)

## Licence & attribution

This work includes material from the **System Reference Document 5.1** ("SRD 5.1")
and the **System Reference Document 5.2** ("SRD 5.2") by Wizards of the Coast LLC,
available at https://www.dndbeyond.com/srd. The SRD 5.1 and SRD 5.2 are licensed
under the Creative Commons Attribution 4.0 International License, available at
https://creativecommons.org/licenses/by/4.0/legalcode.

No other D&D content (Player's Handbook, DMG, Sage Advice, D&D Beyond) is ingested;
questions outside the SRD are answered with an honest refusal.
