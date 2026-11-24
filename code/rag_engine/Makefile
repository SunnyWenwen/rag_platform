.PHONY: install check lint typecheck layers test test-es run smoke image sync-contracts

install:
	uv sync --frozen

check: lint typecheck layers test

lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts

typecheck:
	uv run mypy
	uv run mypy scripts

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

# Drive a running Runtime through the whole Builder flow over HTTP (start it first with `make run`).
# Against a deployed DEV Runtime: make smoke URL=https://... with RAG_SMOKE_MANAGEMENT_USERNAME/PASSWORD set.
# Add SMOKE_ARGS=--rewrite to also query through the company LLM.
URL ?= http://127.0.0.1:8080
smoke:
	uv run python scripts/smoke_dev_runtime.py --base-url $(URL) $(SMOKE_ARGS)

image:
	docker build -t rag-runtime:$$(uv run python -c "import rag_engine; print(rag_engine.__version__)") .

# Inside rag_platform (code/rag_engine) the spec root is ../..; elsewhere pass PLATFORM=<rag_platform path>.
PLATFORM ?= ../..
sync-contracts:
	uv run python scripts/sync_contracts.py $(PLATFORM)
