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

**Normalization** — Scaling a vector to length 1. Sentence-embedding models
typically output normalized vectors, which makes cosine similarity and dot product
give identical rankings.

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

**Chunking** — Splitting source documents into retrieval-sized pieces (~400 tokens,
~50 overlap here, heading-structure first). Chunk size/overlap are experiment
parameters, justified by MLflow runs, never hardcoded on vibes.

**Contextual enrichment** — Prepending a chunk's `heading_path` (e.g.
`Combat > Making an Attack > Sneak Attack`) to its text before embedding, so the
vector carries context the bare chunk text lacks. Cheap and usually wins.

## Evaluation

**Golden set** — Hand-verified Q&A pairs (with grounding sections, edition and
difficulty tags, plus deliberately unanswerable questions) that all retrieval and
generation metrics are computed against. Lives in `evals/golden_set.jsonl`.

**MRR (Mean Reciprocal Rank)** — Retrieval metric: 1/rank of the first relevant
result, averaged over queries. Rewards putting a right answer *high*, not just
somewhere in the top k. 🚩

**Faithfulness** — Generation metric: is every claim in the answer actually
supported by the retrieved chunks? Guards against the model answering from its own
training data instead of the sources. 🚩

**MLflow** — Experiment tracker. Every retrieval/prompt experiment is logged as a
run with parameters, metrics, and git SHA, so "hybrid beats pure vector" is a
reproducible claim, not a memory.
