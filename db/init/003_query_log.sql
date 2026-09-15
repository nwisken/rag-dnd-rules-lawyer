-- One row per /ask: the raw material for the README monitoring section and drift/quality review.
CREATE TABLE IF NOT EXISTS query_log (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question          text NOT NULL,
    -- the /ask edition filter; NULL means both editions were searched (same convention as feedback)
    edition_filter    text CHECK (edition_filter IS NULL OR edition_filter IN ('srd51', 'srd52')),
    -- heading paths of the retrieved chunks, in rank order; stable across re-ingests, unlike chunk
    -- uuids which regenerate every chunking run (label-invariance, same reason the golden set uses paths)
    retrieved_paths   text[] NOT NULL,
    -- retrieval scores, aligned 1:1 with retrieved_paths; empty arrays on a no-hit refusal, never NULL
    scores            double precision[] NOT NULL,
    answer_chars      int NOT NULL,
    -- from the Anthropic response usage; nullable so a generation failure still logs the query
    prompt_tokens     int,
    completion_tokens int,
    latency_ms        int NOT NULL,
    -- links to the vote once the user thumbs this answer; NULL until that round-trip is wired
    feedback_id       uuid REFERENCES feedback(id),
    created_at        timestamptz NOT NULL DEFAULT now()
);
