"""Loader for the golden evaluation set (``evals/golden_set.jsonl``)."""

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class GoldenQuestion:
    """One hand-written evaluation question with its grounding labels."""

    id: str
    question: str
    edition: str | None
    answerable: bool
    grounding: tuple[str, ...]
    expected_answer: str
    difficulty: str


FIELD_NAMES = {f.name for f in fields(GoldenQuestion)}
EDITIONS = {"srd51", "srd52"}
DIFFICULTIES = {"easy", "medium", "hard"}


def validate_records(records: Sequence[Mapping[str, Any]]) -> list[str]:
    """Checks every record against the GoldenQuestion contract, without raising.

    Args:
        records: raw records parsed from the golden set file.

    Returns:
        Every problem found, one message per problem. Empty means valid.
    """
    errors: list[str] = []

    for index, record in enumerate(records):
        # index used in case ID is missing
        where = f"record {index} ({record.get('id', '<no id>')})"

        missing = FIELD_NAMES - record.keys()
        if missing:
            errors.append(f"{where}: missing fields {sorted(missing)}")

        # Any unexpected attributes in records i.e typo
        unknown = record.keys() - FIELD_NAMES
        if unknown:
            errors.append(f"{where}: unknown fields {sorted(unknown)}")

        # Checks below guarded by `in record` so a missing field isn't reported twice
        # null edition i.e question applies to both editions
        if "edition" in record and record["edition"] not in EDITIONS | {None}:
            errors.append(
                f"{where}: edition {record['edition']!r} not in {sorted(EDITIONS)} or null"
            )
        if "difficulty" in record and record["difficulty"] not in DIFFICULTIES:
            errors.append(
                f"{where}: difficulty {record['difficulty']!r} not in {sorted(DIFFICULTIES)}"
            )

        # Empty path would prefix-match every chunk i.e a free recall hit
        if "grounding" in record and any(not path for path in record["grounding"]):
            errors.append(f"{where}: grounding contains an empty string")

        # answerable False exactly when grounding empty, so the two booleans must match
        has_both = {"answerable", "grounding"} <= record.keys()
        if has_both and record["answerable"] != bool(record["grounding"]):
            errors.append(
                f"{where}: answerable={record['answerable']!r} but grounding has "
                f"{len(record['grounding'])} entries"
            )

    #  checks each record has a unique ID
    id_counts = Counter(record["id"] for record in records if "id" in record)
    for record_id, count in sorted(id_counts.items()):
        if count > 1:
            errors.append(f"id {record_id!r} used by {count} records")

    return errors


def to_question(record: Mapping[str, Any]) -> GoldenQuestion:
    """Builds a GoldenQuestion from a record that has already passed validation.

    Args:
        record: one validated record from the golden set file.

    Returns:
        The record as a frozen GoldenQuestion.
    """
    return GoldenQuestion(
        id=record["id"],
        question=record["question"],
        edition=record["edition"],
        answerable=record["answerable"],
        # JSON gives a list, the dataclass needs a tuple to stay hashable
        grounding=tuple(record["grounding"]),
        expected_answer=record["expected_answer"],
        difficulty=record["difficulty"],
    )


def load_golden_set(path: Path) -> list[GoldenQuestion]:
    """Reads the golden set file and returns it as validated GoldenQuestions.

    Args:
        path: path to the JSONL golden set file.

    Returns:
        One GoldenQuestion per line, in file order.

    Raises:
        ValueError: if any record fails validation, listing every problem found.
    """
    # encoding pinned so the SRD's non-ASCII characters survive on any platform
    with path.open(encoding="utf-8") as file:
        records = [json.loads(line) for line in file if line.strip()]

    errors = validate_records(records)
    if errors:
        raise ValueError(f"{path} failed validation:\n" + "\n".join(errors))

    return [to_question(record) for record in records]
