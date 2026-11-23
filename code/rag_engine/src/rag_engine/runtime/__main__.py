"""``python -m rag_engine.runtime``: start one Runtime process (one per Pod)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "rag_engine.runtime.app:create_app",
        factory=True,
        host=os.environ.get("RAG_HOST", "0.0.0.0"),
        port=int(os.environ.get("RAG_PORT", "8080")),
        workers=1,  # Pod-local Ingestion state requires a single process.
        log_config=None,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
