# Retrieval Runtime image. Build from the repository root:
#   docker build -t rag-runtime:0.1.0 .
# Replace the base images with the company mirror if Docker Hub / ghcr.io are not reachable.
ARG PYTHON_IMAGE=python:3.12-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PYTHON=python3.12
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE}
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin rag
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY resources /app/resources
# The bge-m3 tokenizer is baked in; the Runtime never downloads models at startup.
# Put BAAI/bge-m3 tokenizer.json at models/bge-m3/tokenizer.json before building (see models/README.md).
COPY models/bge-m3/tokenizer.json /opt/models/bge-m3/tokenizer.json
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    RAG_RESOURCES_FILE=/app/resources/dev.yaml \
    RAG_PORT=8080
USER 10001
EXPOSE 8080
# One process per Pod: Ingestion occupancy, queue and Runs live in this process's memory.
CMD ["python", "-m", "rag_engine.runtime"]
