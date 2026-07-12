# Rules Lawyer — a D&D 5e RAG Assistant

Answers Dungeons & Dragons 5th Edition rules questions with cited sources, aware of
the difference between the 2014 rules (SRD 5.1) and the revised 2024 rules (SRD 5.2).

## Why this isn't another RAG tutorial

Most RAG demos are a LangChain tutorial with a different PDF. This project differs by:

1. **Hybrid retrieval** (pgvector cosine + Postgres full-text, fused with RRF) — rules
   text is jargon-dense ("opportunity attack", "bonus action"); keyword search
   materially beats pure vector search here, and we prove it with numbers.
2. **Version-aware answers** via metadata filtering across two rule editions.
3. **Evaluated, not vibes-checked**: a golden Q&A set, retrieval + generation metrics
   tracked in MLflow, and evals gating CI.
4. **Actually deployed**: containerised, CI/CD to Azure Container Apps, monitored.

## Status

🚧 Phase 1 (walking skeleton) in progress. Eval results table, screenshots, and the
public URL land here as the phases complete.

## Local setup

```sh
cp .env.example .env
docker compose up -d      # Postgres 16 + pgvector
uv sync                   # Python 3.12 environment
```

## Licence & attribution

This work includes material from the **System Reference Document 5.1** ("SRD 5.1")
and the **System Reference Document 5.2** ("SRD 5.2") by Wizards of the Coast LLC,
available at https://www.dndbeyond.com/srd. The SRD 5.1 and SRD 5.2 are licensed
under the Creative Commons Attribution 4.0 International License, available at
https://creativecommons.org/licenses/by/4.0/legalcode.

No other D&D content (Player's Handbook, DMG, Sage Advice, D&D Beyond) is ingested;
questions outside the SRD are answered with an honest refusal.
