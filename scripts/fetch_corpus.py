"""Fetch the SRD corpus into ``data/raw/``.

Downloads two kinds of file per edition:

* **PDF ground truth** (official Wizards of the Coast, CC-BY-4.0) — what
  ``verify_corpus.py`` checks the markdown against.
* **Markdown for chunking** (the your5e mirror, CC-BY-4.0) — what ``parse.py``
  walks. Both the cleaned and ``.untouched`` conversions are kept.

Reproducible by construction: every file is pinned to an immutable URL (the
markdown mirror to a specific commit, not a moving branch) and verified against
a recorded SHA-256, so anyone who runs this gets byte-for-byte the corpus the
project was built and evaluated against. Re-runs are idempotent — a file whose
hash already matches is skipped.

Usage:
    python scripts/fetch_corpus.py            # fetch missing / changed files
    python scripts/fetch_corpus.py --force    # re-download everything
"""

import argparse
import hashlib
import shutil
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# your5e/5e-srd-markdown pinned to an immutable commit: a branch like HEAD moves,
# a commit SHA does not, so the markdown can never drift under us between runs.
_YOUR5E_COMMIT = "f1f5060fd975aa2ffc3e4b336560ded479934d80"
_YOUR5E_RAW = f"https://raw.githubusercontent.com/your5e/5e-srd-markdown/{_YOUR5E_COMMIT}"
_DNDBEYOND = "https://media.dndbeyond.com/compendium-images/srd"

# scripts/ -> repo root -> data/raw
DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


@dataclass(frozen=True)
class Source:
    """One corpus file: where it lives locally, where to fetch it, its hash."""

    filename: str
    url: str
    sha256: str


MANIFEST: tuple[Source, ...] = (
    # --- PDF ground truth (official WotC) ---
    Source(
        "SRD_CC_v5.1.pdf",
        f"{_DNDBEYOND}/5.1/SRD_CC_v5.1.pdf",
        "2504d2a0abb0a4d491a939be4f17910a2dde0312570ab8d208080225ccf0a1f0",
    ),
    Source(
        "SRD_CC_v5.2.1.pdf",
        f"{_DNDBEYOND}/5.2/SRD_CC_v5.2.1.pdf",
        "8974902d109d6e63672d7c490bde9ccf052410503d9cfa768237154fbc5e3d87",
    ),
    # --- Markdown for chunking (your5e mirror) ---
    Source(
        "SRD_CC_v5.1.md",
        f"{_YOUR5E_RAW}/dnd/51/SRD_CC_v5.1.md",
        "f3ef56ef552afb8ed6b0fb36b9e74bcce5010b52e05cd730d3a32272bc36fcc8",
    ),
    Source(
        "SRD_CC_v5.1.untouched.md",
        f"{_YOUR5E_RAW}/dnd/51/SRD_CC_v5.1.untouched.md",
        "ffa8e81a3d292b912fe6f7bab05af4299f78810e1adc2d5fd946066ff279e438",
    ),
    Source(
        "SRD_CC_v5.2.1.md",
        f"{_YOUR5E_RAW}/dnd/521/SRD_CC_v5.2.1.md",
        "e4f4803e7cef3d33f42555616fae75abc72ec4f3d79ba1bf344afc906504bec2",
    ),
    Source(
        "SRD_CC_v5.2.1.untouched.md",
        f"{_YOUR5E_RAW}/dnd/521/SRD_CC_v5.2.1.untouched.md",
        "ac370e134a876fb930f62a1d99e779d1a851c1623d06d8164c6a73dd862b5ae4",
    ),
)


def sha256_of(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in 1 MiB blocks to bound memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dest: Path) -> None:
    """Stream ``url`` to ``dest``.

    Sends an explicit User-Agent because some CDNs reject urllib's default one.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "ruleslawyer-fetch"})
    with urllib.request.urlopen(request, timeout=30) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def fetch(source: Source, *, force: bool) -> str:
    """Fetch one source if needed and verify its hash. Returns a status word."""
    dest = DATA_RAW / source.filename
    if dest.exists() and not force and sha256_of(dest) == source.sha256:
        return "skip (present)"
    download(source.url, dest)
    actual = sha256_of(dest)
    if actual != source.sha256:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"{source.filename}: sha256 mismatch\n"
            f"  expected {source.sha256}\n"
            f"  got      {actual}"
        )
    return "downloaded"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch the SRD corpus into data/raw/.")
    parser.add_argument(
        "--force", action="store_true", help="re-download even if a matching file is present"
    )
    args = parser.parse_args()

    DATA_RAW.mkdir(parents=True, exist_ok=True)
    for source in MANIFEST:
        print(f"  {fetch(source, force=args.force):16} {source.filename}")
    print(f"\nCorpus ready in {DATA_RAW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
