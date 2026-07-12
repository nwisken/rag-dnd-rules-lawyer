CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    content      text NOT NULL,
    content_tsv  tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    embedding    vector(384),
    edition      text NOT NULL CHECK (edition IN ('srd51', 'srd52')),
    doc_section  text,
    heading_path text,
    page_ref     text,
    token_count  int,
    created_at   timestamptz NOT NULL DEFAULT now()
);
