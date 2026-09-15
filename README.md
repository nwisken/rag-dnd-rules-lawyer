# Rules Lawyer — a D&D 5e RAG Assistant

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

Phase 3 (answer quality) complete: citation-forced prompting, refusal behaviour for
non-SRD questions, generation evals, and a thumbs up/down feedback endpoint. Screenshots
and public URL land in later phases.

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
