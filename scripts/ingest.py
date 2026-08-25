"""Ingest the SRD corpus into the database as embedded chunks."""

import argparse
from pathlib import Path

from verify_corpus import is_corpus_valid

from ruleslawyer.ingest.chunk import chunk_sections
from ruleslawyer.ingest.embed import DEFAULT_MODEL, Embedder, embedding_input
from ruleslawyer.ingest.load import connect, load_chunks
from ruleslawyer.ingest.parse import parse_markdown

CORPORA = [
    (Path("data/raw/SRD_CC_v5.1.pdf"), Path("data/raw/SRD_CC_v5.1.md"), "srd51"),
    (Path("data/raw/SRD_CC_v5.2.1.pdf"), Path("data/raw/SRD_CC_v5.2.1.md"), "srd52")
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest SRD corpus into the database.")
    parser.add_argument("--chunk-size", type=int, default=400,
                        help="max tokens per chunk (default: 400)")
    parser.add_argument("--overlap", type=int, default=50,
                        help="overlap tokens between chunks (default: 50)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"embedding model name (default: {DEFAULT_MODEL})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"Config: chunk_size={args.chunk_size}, overlap={args.overlap}, model={args.model}")

    embedder = Embedder(model_name=args.model)
    conn = connect()

    for pdf_path, markdown_path, edition in CORPORA:
        if is_corpus_valid(pdf_path, markdown_path):
            print(f"Corpus: {markdown_path} is valid")
            markdown_text_raw = markdown_path.read_text()
            markdown_parsed = parse_markdown(markdown_text_raw)
            markdown_chunks = chunk_sections(markdown_parsed, count_tokens=embedder.count_tokens,
                                             max_tokens=args.chunk_size,
                                             overlap_tokens=args.overlap)
            enriched = [embedding_input(chunk) for chunk in markdown_chunks]
            embed_text = embedder.embed_texts(enriched)

            inserted = load_chunks(conn, markdown_chunks, embed_text, edition)
            print("Inserted: ", inserted)
        else:
            print(f"Corpus: {markdown_path} is invalid")

if __name__ == "__main__":
    main()
