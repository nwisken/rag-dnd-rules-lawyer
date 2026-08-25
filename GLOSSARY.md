# Glossary

Plain-English definitions of the technical terms used in this project, in roughly the
order you meet them in the pipeline. Interview-relevant terms are flagged 🚩.

## Embeddings & similarity

**Embedding** — A fixed-length list of floats (for our model, 384) that a neural
network produces from a piece of text. The geometry encodes meaning: texts with
similar meaning map to nearby points, even with no shared words. Retrieval becomes
"find the nearest vectors."

**Embedding model** — The network that produces embeddings. Two models evaluated in
this project: `bge-small-en-v1.5` (384 dims, 512-token window) and
`all-MiniLM-L6-v2` (384 dims, 256-token window). The dimension count is a property
of the model, not a knob: changing to a model with a different dimension means
re-embedding the whole corpus *and* altering the `vector(N)` column. Even same-
dimension models produce incomparable coordinate spaces — comparing vectors from two
models computes fine and means nothing (silent wrongness, worse than a crash). 🚩

**Context window (embedding)** — The maximum number of tokens an embedding model
accepts. Text beyond this limit is silently truncated — the tail is lost from the
vector with no error. This creates a hard coupling between chunk size and model
choice: 400-token chunks exceed MiniLM's 256-token window, losing content. The
chunking experiments showed this concretely: MiniLM at 200 tokens (fits the window)
tied bge-small's best recall and posted the highest MRR; MiniLM at 400 tokens
(truncated) dropped recall. Rule: chunk size must respect the embedding model's
context window, or retrieval quality degrades invisibly. 🚩

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

**Recall / recall@k** — The fraction of the things that *should* have been returned
that actually were. Careful: the word is used in two different places in this project.
In *indexing*, "recall" means how many of the true nearest neighbours an ANN index
found — exact search is recall 1.0 by definition, and ANN indexes trade recall away
for speed. In *evaluation*, it means how many of a golden question's grounding
sections appeared in the top k — see **fractional recall@k** under Evaluation. Same
word, same shape, different denominators. 🚩

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

**`ts_rank`** — Postgres function that scores how well a document matches a
full-text query by counting matching terms and weighting by frequency. Higher =
more relevant. Simple and fast, but treats terms independently — "bonus" and
"action" each contribute score whether they appear together or pages apart.

**`ts_rank_cd`** (cover density) — Like `ts_rank`, but also rewards matching
terms appearing *close together*. Internally it measures the width of the
tightest "cover" (the smallest span of text containing all query terms) and
scores inversely to that width. For multi-word rules queries like "sneak attack
thrown dagger", this consistently outranks passages where the terms are scattered.
The cost difference from `ts_rank` is negligible. This project uses `ts_rank_cd`.

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

**Grounding section** — The place in the SRD that actually contains the answer to a
golden-set question, recorded as a `heading_path` prefix (e.g.
`Rogue > Class Features > Sneak Attack`). A retrieved chunk counts as relevant if its
`heading_path` starts with one of them. A question may have several: "does Sneak
Attack work with a thrown dagger?" needs both the Sneak Attack rule *and* the finesse
definition under Weapon Properties, and retrieving only one of them is why v0.1
refused to answer.

**Label invariance** 🚩 — The rule that eval labels must not be expressed in terms of
the thing you're experimenting on. Grounding is recorded as a heading path (a fact
about the *document*) rather than as chunk UUIDs (a fact about the *index*), because
every chunk-size experiment regenerates the UUIDs — labels tied to them would go stale
on the first run and the "experiment" would be measuring label drift, not retrieval.
The general form: name the target in the most stable vocabulary that still identifies
it.

**Fractional recall@k** — This project's retrieval metric: for one question,
(grounding sections found in the top k) / (total grounding sections), then averaged
over questions. Partial credit — finding 1 of 2 required sections scores 0.5, so the
number moves as retrieval improves rather than flipping between 0 and 1.

**Precision@k** — The mirror of recall: of the k results returned, what fraction were
relevant. Recall asks "did we miss anything?", precision asks "how much junk came
with it?". Precision@k is bounded by k, so with a fixed small k it mostly restates
recall; recall + MRR is the more informative pair here. In a RAG pipeline low
precision isn't free, though — irrelevant chunks eat context window and dilute the
generator's attention.

**Hit rate@k (the recall@k impostor)** 🚩 — Scores 1 if *any* grounding section is in
the top k, else 0. Widely published under the name "recall@k", which is why it's worth
being able to name the difference. It would have scored the v0.1 Sneak Attack failure
a perfect 1.0 — the Sneak Attack chunk *was* retrieved — while the app refused to
answer for want of the finesse definition. A metric that reports success on your
motivating failure case is worse than no metric.

**MRR (Mean Reciprocal Rank)** — Retrieval metric: 1/rank of the first relevant
result, averaged over queries (rank 1 → 1.0, rank 2 → 0.5, nothing relevant → 0).
Rewards putting a right answer *high*, not just somewhere in the top k. Complements
recall rather than duplicating it: recall asks whether everything needed was found,
MRR asks how near the top the first good hit landed. Only ever looks at the first
relevant result, so on its own it's blind to multi-section questions. 🚩

**MMR (Maximal Marginal Relevance)** — Not a metric and not a typo of MRR, despite
the collision. It's a *selection* strategy for building a result list: pick each next
result to maximise relevance to the query minus similarity to what's already picked,
with a λ knob trading the two off. The problem it solves is a top-k of five
near-identical chunks (which overlap-heavy chunking can cause) crowding out the one
other section the answer needs. A Phase 5 candidate here, not something we currently
run. 🚩

**LLM-as-judge** — Using an LLM to score another LLM's output against a rubric, when the
quality you care about ("is this grounded?", "does this address the question?") is too
fuzzy for a string match. This project hand-rolls one for all three generation metrics:
each is a *versioned prompt* + a `Judge` method that calls a **pinned** model + a *pure
scorer* that turns the verdict into a number. Strengths: captures nuance no regex can, and
needs no ground-truth answer. Weaknesses: noisy (the judge wavers run-to-run, hence the CI
tolerance), costs an API call per item, and inherits the judge model's blind spots — so the
judge is pinned and its prompt versioned for reproducibility. 🚩

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

**Answer relevance** — Generation metric: does the answer actually address the
question that was asked? Independent of faithfulness — an answer can be faithful to its
sources yet answer a different question, or be on-topic yet unsupported. This project
measures it with an LLM-as-judge **rubric**: the judge classifies the answer as `full` /
`partial` / `none`, mapped to 1.0 / 0.5 / 0.0 and averaged over the answerable golden
questions. A wrong refusal on an answerable question scores `none`, so the metric also
penalises over-refusal. Correctness is deliberately out of scope — a confidently wrong
but on-topic answer is still relevant; faithfulness is the metric that catches wrongness.
🚩

**Answer relevance via reverse-generation (RAGAS's method)** — The notable alternative
to the rubric judge, worth being able to describe. Instead of rating relevance directly,
generate N hypothetical questions *from the answer*, embed them, and take the mean cosine
similarity to the real question's embedding; high similarity ⇒ the answer is "about" the
same question. Clever because it needs no ground-truth answer, but it adds moving parts
(reverse-generation + an embedding model + cosine) and can be gamed by generic answers
that sit near everything. This project ships the rubric judge instead — simpler, one
call, and a pure label→number mapping that unit-tests without an LLM. 🚩

**Refusal accuracy** — Generation metric over the *deliberately unanswerable* golden
questions: the fraction the app correctly declined ("the SRD doesn't cover this") instead
of inventing an answer. The subtle part is what counts as a failure: **substituting a
similarly named rule** — answering about the halfling Lucky *trait* when asked about the
Lucky *feat* — is an attempt, not a refusal, and must score as wrong. A metric that let
substitution pass would reward the exact behaviour the honest-refusal feature exists to
prevent. Baseline here is 1.000 (all 5 refused). 🚩

**Model pinning (snapshot vs alias)** — A reproducibility discipline. A floating **alias**
like `claude-haiku-4-5` silently points at whatever the current version is; a dated
**snapshot** like `claude-haiku-4-5-20251001` is frozen. This project pins the *judge* to a
snapshot (a measuring stick that must not move) while leaving the *generator* on the alias
(a hyperparameter we deliberately tune). Mixing them up means a model upgrade quietly shifts
your eval scores with no code change. 🚩

**Defensive output parsing** — The rule that you never trust an LLM to honour an output
format from the prompt alone. Our judge was told "return ONLY JSON" and still wrapped it in
a ```json code fence, which broke `json.loads` at character 0. The fix is code, not a
sterner prompt: `_strip_to_json` takes the substring from the first `{` to the last `}`,
surviving fences and stray prose — and because it's a pure function it unit-tests without an
LLM. General lesson: parse model output like untrusted input. 🚩

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
