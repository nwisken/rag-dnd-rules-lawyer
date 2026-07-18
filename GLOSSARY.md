# Glossary

Plain-English definitions of the technical terms used in this project, in roughly the
order you meet them in the pipeline. Interview-relevant terms are flagged 🚩.

## Embeddings & similarity

**Embedding** — A fixed-length list of floats (for our model, 384) that a neural
network produces from a piece of text. The geometry encodes meaning: texts with
similar meaning map to nearby points, even with no shared words. Retrieval becomes
"find the nearest vectors."

**Embedding model** — The network that produces embeddings. Ours is
`bge-small-en-v1.5` (384 dimensions). The dimension count is a property of the model,
not a knob: changing models means re-embedding the whole corpus *and* altering the
`vector(384)` column.

**Token / tokenizer** 🚩 — Embedding models don't read words or characters; they read
*tokens*: pieces from a fixed vocabulary the model learned, often whole common words
("attack") but sub-word fragments for rarer ones ("Fireball" → "Fire" + "ball").
The tokenizer is the deterministic function that maps text to tokens. Rule of thumb:
1 token ≈ ¾ of an English word. Tokens matter to us for exactly one reason: **models
have a maximum input length in tokens** (512 for bge-small); text beyond it is
silently truncated — invisible data loss. So tokens are our *unit of measurement* for
chunk budgets. We never split text *on* tokens (that would cut mid-word); we split on
meaning boundaries and *measure* the pieces in tokens.

**Normalization** — Scaling a vector to length 1. Sentence-embedding models
typically output normalized vectors, which makes cosine similarity and dot product
give identical rankings.

**Asymmetric embedding / query instruction** — Treating queries and documents
differently at embed time. Short questions and long passages are different kinds of
text and land in slightly different vector neighbourhoods; BGE models were trained so
that prefixing a *query* (never a passage) with an instruction string ("Represent
this sentence for searching relevant passages: ...") nudges its vector toward the
passage region. For bge-*-v1.5 the authors call the gain small and optional, so this
project ships Phase 1 symmetric (no prefix) and tests prefix-vs-no-prefix as a
Phase 2 MLflow experiment.

**Cosine similarity** — Similarity as the cosine of the angle between two vectors
(1 = same direction, 0 = unrelated). Ignores magnitude, which for text embeddings is
mostly noise; direction carries the semantics. pgvector operator: `<=>` (cosine
*distance*, i.e. 1 − similarity).

## Search & indexing

**Exact (brute-force) search / sequential scan** — Compare the query vector against
every stored vector, sort, take the top k. Perfect recall by definition; cost grows
linearly with corpus size, written O(n). At our scale (thousands of chunks) it runs in
milliseconds, which is why Phase 1 deliberately has **no vector index**. 🚩

**ANN (Approximate Nearest Neighbour)** — A family of index structures that find
*probably* the nearest vectors without comparing against every row, trading a small
loss of recall for a large speed-up. Only worth it when exact search is measurably
too slow (large corpora and/or high query rates). 🚩

**Recall / recall@k** — Of the true k nearest neighbours (or true grounding
sections, in evals), the fraction the system actually returned. Exact search is
recall 1.0; ANN indexes trade recall for speed via tunable parameters. 🚩

**HNSW (Hierarchical Navigable Small World)** — The strongest general-purpose ANN
index, and one of two in pgvector. Builds a layered graph of neighbour links: sparse
top layers make long jumps, dense lower layers make fine steps — like navigating with
country → city → street maps. Queries cost roughly O(log n). Pros: fast, high recall,
incremental inserts. Cons: memory-hungry, slow to build, approximate. Tuning knobs:
`m`, `ef_construction`, `ef_search` (higher = better recall, more cost). 🚩

**IVFFlat (Inverted File with Flat storage)** — pgvector's other ANN index.
"Inverted File" = vectors are clustered into buckets ("lists") up front and a query
scans only the few buckets nearest to it; "Flat" = vectors inside the buckets are
stored uncompressed, at full precision (contrast IVF-PQ, which compresses them).
Cheaper to build and lighter on memory than HNSW, but generally lower recall at the
same speed, and it must be built after the data is loaded (it clusters what's there).

## Retrieval (this app's pipeline)

**pgvector** — Postgres extension adding a `vector` column type, distance operators,
and ANN indexes. Lets one Postgres query combine vector similarity, keyword search,
and metadata filters — the reason we don't run a dedicated vector database. 🚩

**Full-text search / `tsvector`** — Postgres's built-in keyword search.
`to_tsvector` reduces text to normalized searchable tokens; our `content_tsv` column
is generated automatically from `content` so it can never drift out of sync. Matters
here because rules jargon ("bonus action") is exactly what keyword search is good at.

**Hybrid retrieval** — Running vector search *and* keyword search for the same
query, then merging the two ranked lists. The project's core claim is that hybrid
beats pure vector on rules text, proven with eval numbers. 🚩

**RRF (Reciprocal Rank Fusion)** — The merge step for hybrid retrieval: each result
scores 1/(k + rank) in each list, scores summed across lists. Uses only ranks, never
raw scores, so it needs no score normalization between very different scorers. 🚩

**Chunk** 🚩 — The atomic unit of retrieval: one contiguous piece of source text,
sized to fit the embedding model's input limit, stored as one row in the `chunks`
table with one embedding. When the retriever answers a query, what it returns is
chunks. Too big → the vector is a mushy average of many topics and won't fit the
model's 512-token limit; too small → a chunk lacks the context to be understood
alone ("the target takes 8d6 fire damage" — of *what*?).

**Chunking** — Splitting source documents into retrieval-sized pieces (~400 tokens,
~50 overlap here, heading-structure first). Chunk size/overlap are experiment
parameters, justified by MLflow runs, never hardcoded on vibes.

**Overlap** — Repeating the last ~50 tokens of one chunk at the start of the next, so
a fact straddling the cut exists intact in at least one chunk and each chunk starts
with enough context to make sense read alone. Cost: a little storage/duplication.

**Contextual enrichment** — Prepending a chunk's `heading_path` (e.g.
`Combat > Making an Attack > Sneak Attack`) to its text before embedding, so the
vector carries context the bare chunk text lacks. Cheap and usually wins.

## Evaluation

**W-shingling / n-gram containment** — Technique for asking "is document A's content
present in document B?" without caring about ordering or formatting. Slide a window of
n consecutive words (a *shingle*) over A; each shingle is a near-unique fingerprint of
one specific sentence. Score = fraction of A's shingles found anywhere in B. Missing
text ⇒ its shingles all vanish ⇒ score drops proportionally. n is a dial: too small
(1–3) and common phrases match everywhere, inflating the score; too large (50) and
one injected artifact (a page number mid-sentence) breaks every shingle spanning it,
deflating it. ~8 is conventional. Used by plagiarism detectors and search-engine
dedup; used here by `verify_corpus.py` to prove the markdown mirror contains the
PDF's content before we chunk from it. 🚩

**Golden set** — Hand-verified Q&A pairs (with grounding sections, edition and
difficulty tags, plus deliberately unanswerable questions) that all retrieval and
generation metrics are computed against. Lives in `evals/golden_set.jsonl`.

**MRR (Mean Reciprocal Rank)** — Retrieval metric: 1/rank of the first relevant
result, averaged over queries. Rewards putting a right answer *high*, not just
somewhere in the top k. 🚩

**Faithfulness** — Generation metric: is every claim in the answer actually
supported by the retrieved chunks? Guards against the model answering from its own
training data instead of the sources. Computed by a two-step LLM-as-judge pipeline
(this is what RAGAS does): (1) a judge LLM decomposes the answer into atomic factual
claims; (2) for each claim it answers "can this be inferred from the retrieved
chunks alone?" — its own world knowledge doesn't count as evidence. Score =
supported claims / total claims. An answer can be *correct* but *unfaithful* if the
right fact never appeared in the retrieved chunks. Noisy run-to-run: judges split
claims differently and waver on borderline inferences, so scores jitter a few
points — which is why the CI gate has a tolerance. 🚩

**Eval gate (tolerance + floor)** — The CI rule deciding whether a PR's eval scores
pass. Two checks, both must hold: **tolerance** — the score may not drop more than
0.05 below the tracked baseline (the best previous MLflow run); catches
*regressions* while absorbing judge noise. **Floor** — the score must be ≥ 0.70 no
matter what the baseline says; a fixed tripwire for "outright broken" (and covers
the first run, when no baseline exists). A tolerance sized below the metric's
natural noise makes CI flaky, and flaky gates get ignored — worse than loose ones.
Both numbers are revisable once real eval runs exist, via a visible MLflow-justified
change. 🚩

**MLflow** — Experiment tracker. Every retrieval/prompt experiment is logged as a
run with parameters, metrics, and git SHA, so "hybrid beats pure vector" is a
reproducible claim, not a memory.
