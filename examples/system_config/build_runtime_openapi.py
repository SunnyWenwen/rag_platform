"""Bundle the DEV OpenAPI and the referenced repository schemas for offline use."""

import argparse
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin

REPO = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO / "openapi/runtime.dev.v1.json"


def at_pointer(document, fragment):
    for token in fragment.removeprefix("#").split("/")[1:]:
        key = token.replace("~1", "/").replace("~0", "~")
        document = document[int(key) if isinstance(document, list) else key]
    return document


def build_bundle():
    openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    sources = {}
    for path in sorted((REPO / "schemas").glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        name = path.name.removesuffix(".schema.json").replace(".", "_")
        sources[path.as_uri()] = sources[schema["$id"]] = (name, schema)

    bundled = {}

    def visit(value, base):
        if isinstance(value, list):
            return [visit(item, base) for item in value]
        if not isinstance(value, dict):
            return value
        return {
            key: resolve(item, base) if key == "$ref" else visit(item, base)
            for key, item in value.items()
        }

    def resolve(ref, base):
        if base == OPENAPI_PATH.as_uri() and ref.startswith("#"):
            return ref
        target, fragment = urldefrag(ref)
        uri = urljoin(base, target) if target else base
        if uri not in sources:
            raise ValueError(f"Unresolved schema {ref!r} in {base}")
        resource_name, data = sources[uri]
        name = resource_name
        for token in fragment.split("/")[1:]:
            if token not in {"$defs", "properties"}:
                name += "__" + token
        if name not in bundled:
            # Reserve the component before following recursive Document and filter references.
            bundled[name] = {}
            selected = at_pointer(data, fragment)
            bundled[name] = visit(
                {key: value for key, value in selected.items() if key not in {"$schema", "$id", "$defs"}},
                data["$id"],
            )
        return f"#/components/schemas/{name}"

    result = visit(openapi, OPENAPI_PATH.as_uri())
    result["components"]["schemas"] = bundled
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Destination for the self-contained OpenAPI JSON")
    args = parser.parse_args()
    args.output.write_text(json.dumps(build_bundle(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
