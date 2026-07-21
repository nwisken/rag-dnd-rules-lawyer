"""Ingest the SRD corpus into the database as embedded chunks."""

from pathlib import Path

from verify_corpus import is_corpus_valid

CORPORA = [
    (Path("data/raw/SRD_CC_v5.1.pdf"), Path("data/raw/SRD_CC_v5.1.md")),
    (Path("data/raw/SRD_CC_v5.2.1.pdf"), Path("data/raw/SRD_CC_v5.2.1.md")),
]


def main() -> None:
    for pdf_path, markdown_path in CORPORA:
        if is_corpus_valid(pdf_path, markdown_path):
            print(f"Corpus: {markdown_path} is valid")
            # TODO ingest corpus

        else:
            print(f"Corpus: {markdown_path} is invalid — skipping")
            continue


if __name__ == "__main__":
    main()
