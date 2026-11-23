.PHONY: install check lint typecheck layers test test-es run image sync-contracts

install:
	uv sync --frozen

check: lint typecheck layers test

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy

layers:
	uv run lint-imports

test:
	uv run pytest -q

# Needs RAG_TEST_ES_URL (and RAG_TEST_ES_USERNAME / RAG_TEST_ES_PASSWORD) for the PLED test cluster.
test-es:
	uv run pytest -q -m es tests/test_es_store.py

# Local demo: in-memory index, hash embeddings, fixture resources. Not for real data.
run:
	RAG_MANAGEMENT_USERNAME=mock RAG_MANAGEMENT_PASSWORD=mock RAG_EMBEDDING_BACKEND=hash \
		uv run python -m rag_engine.runtime

image:
	docker build -t rag-runtime:$$(uv run python -c "import rag_engine; print(rag_engine.__version__)") .

# Inside rag_platform (code/rag_engine) the spec root is ../..; elsewhere pass PLATFORM=<rag_platform path>.
PLATFORM ?= ../..
sync-contracts:
	uv run python scripts/sync_contracts.py $(PLATFORM)
