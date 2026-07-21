"""Ingest the SRD corpus into the database as embedded chunks."""

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


def main() -> None:

    embedder = Embedder(model_name=DEFAULT_MODEL)
    conn = connect()


    for pdf_path, markdown_path, edition in CORPORA:
        if is_corpus_valid(pdf_path, markdown_path):
            print(f"Corpus: {markdown_path} is valid")
            markdown_text_raw = markdown_path.read_text()
            markdown_parsed = parse_markdown(markdown_text_raw)
            markdown_chunks = chunk_sections(markdown_parsed, count_tokens=embedder.count_tokens,
                                             max_tokens=400, overlap_tokens=50)
            enriched = [embedding_input(chunk) for chunk in markdown_chunks]
            embed_text = embedder.embed_texts(enriched)

            # ingesting into SQL
            inserted = load_chunks(conn, markdown_chunks, embed_text,edition)
            print("Inserted: ", inserted)
        else:
            print(f"Corpus: {markdown_path} is invalid")

if __name__ == "__main__":
    main()
