# Rules Lawyer — task runner.
# On Windows without make, run the underlying commands directly (they're one-liners).

.PHONY: db-up db-down fetch-corpus lint test eval

db-up:
	docker compose up -d db

db-down:
	docker compose down

fetch-corpus:
	@echo "TODO(phase 1): download SRD 5.1 from its official CC-BY-4.0 source into data/raw/"
	@exit 1

lint:
	uv run ruff check src tests
	uv run mypy

test:
	uv run pytest

eval:
	@echo "TODO(phase 2): run retrieval + generation evals against evals/golden_set.jsonl"
	@exit 1
