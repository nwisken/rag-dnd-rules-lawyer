CREATE TABLE IF NOT EXISTS feedback (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question         text NOT NULL,
    answer           text NOT NULL,
    -- nullable: the UI's "Both" edition maps to NULL, same as the /ask filter
    edition          text CHECK (edition IS NULL OR edition IN ('srd51', 'srd52')),
    verdict          text NOT NULL CHECK (verdict IN ('up', 'down')),
    -- heading paths shown when the user voted; nullable so a refusal (no sources) still records
    retrieved_paths  text[],
    created_at       timestamptz NOT NULL DEFAULT now()
);
