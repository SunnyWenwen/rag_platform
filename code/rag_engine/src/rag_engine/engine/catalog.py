"""The Runtime Catalog: delivered built-in Components and the deployment's resources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_engine.contracts import check, load_json, schema_ref
from rag_engine.core.canonical import sha256_hex
from rag_engine.core.resources import RuntimeResources

# Built-in Components this Runtime version executes. The Catalog only lists these, so the
# Builder cannot offer a method the Runtime cannot run.
IMPLEMENTED: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("import", "platform", "1.0.0"),
        ("parsing", "passthrough", "1.0.0"),
        ("chunking", "recursive", "1.0.0"),
        ("embedding", "dense", "1.0.0"),
        ("indexing", "elasticsearch", "1.0.0"),
        ("inference_input", "platform", "1.0.0"),
        ("query_transformation", "none", "1.0.0"),
        ("retrieval", "builtin", "1.0.0"),
        ("rerank", "none", "1.0.0"),
    }
)
REMOTE_ADAPTER_VERSIONS = frozenset({"1.0.0"})


@dataclass(frozen=True)
class Catalog:
    runtime_ref: str
    catalog_revision: str
    descriptors: tuple[dict[str, Any], ...]
    resources: RuntimeResources

    def descriptor(self, module: str, component_id: str, version: str) -> dict[str, Any] | None:
        for item in self.descriptors:
            if (item["module"], item["component_id"], item["component_version"]) == (module, component_id, version):
                return item
        return None

    def response(self) -> dict[str, Any]:
        return {
            "runtime_ref": self.runtime_ref,
            "catalog_revision": self.catalog_revision,
            "descriptors": list(self.descriptors),
            "resources": self.resources.catalog_view(),
        }


def build_catalog(runtime_ref: str, resources: RuntimeResources) -> Catalog:
    source = load_json("catalog/descriptors.fixture.json")
    descriptors = tuple(
        item
        for item in source["descriptors"]
        if (item["module"], item["component_id"], item["component_version"]) in IMPLEMENTED
    )
    view = resources.catalog_view()
    revision = "catalog-" + sha256_hex({"descriptors": list(descriptors), "resources": view})[:12]
    catalog = Catalog(runtime_ref, revision, descriptors, resources)
    check(schema_ref("runtime_catalog.draft.schema.json"), catalog.response())
    return catalog
