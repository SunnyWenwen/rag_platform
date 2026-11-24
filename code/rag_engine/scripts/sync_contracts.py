"""Copy the shared contracts from a rag_platform checkout into this repository.

Usage: uv run python scripts/sync_contracts.py ../rag_platform

The Builder and the Runtime ship the same JSON Schemas. Never edit the vendored copies;
change rag_platform first, then sync and run the tests.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/rag_engine/contracts/data"
FIXTURES = ROOT / "tests/fixtures"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    platform = Path(sys.argv[1]).resolve()
    for schema in sorted((platform / "schemas").glob("*.schema.json")):
        shutil.copy2(schema, DATA / "schemas" / schema.name)
    shutil.copy2(platform / "openapi/runtime.dev.v1.json", DATA / "openapi/runtime.dev.v1.json")
    examples = platform / "examples/system_config"
    # builder_form.descriptors.json is the full Descriptor registry; the Runtime Catalog lists
    # the entries in engine/catalog.py IMPLEMENTED.
    (DATA / "catalog").mkdir(exist_ok=True)
    shutil.copy2(examples / "builder_form.descriptors.json", DATA / "catalog/descriptors.json")
    for name in ("runtime_http.examples.json", "index_fingerprint.v1.example.json", "local_memory.remote_parsing.json"):
        shutil.copy2(examples / name, FIXTURES / name)
    commit = subprocess.run(
        ["git", "-C", str(platform), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "-C", str(platform), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    (DATA / "SOURCE").write_text(f"rag_platform {branch} {commit}\n", encoding="utf-8")
    print(f"synced contracts from {platform} ({branch} {commit[:12]}); now run: make check")


if __name__ == "__main__":
    main()
