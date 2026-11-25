"""Build and serve the React Builder and its management API."""

import argparse
import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from router_service import (
    DEMO_INIT_AUTH, OPERATIONS, SYSTEM_ROUTE, InputError, JsonHandler, Reply, UpstreamError,
    as_json, exchange, require_object, required_text, router_error, validate_apis,
)


ROOT = Path(__file__).resolve().parent
WORKSPACES = {
    "customer-support": "Customer Support",
    "engineering": "Engineering",
    "operations": "Operations",
}
META_SCHEMA = json.loads((ROOT / "config-schema.meta.schema.json").read_text())
META_VALIDATOR = Draft202012Validator(META_SCHEMA)
SYSTEM_CONFIG_ROUTE = re.compile(r"/api/systems/([a-f0-9-]{36})")
SYSTEM_EXPORT_ROUTE = re.compile(r"/api/systems/([a-f0-9-]{36})/export")
PROVIDER_CONFIG_ROUTE = re.compile(r"/api/providers/(demo|mock-retrieval|[a-f0-9-]{36})")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/provider-guide": ("provider-guide.html", "text/html; charset=utf-8"),
    "/app.js": ("dist/app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/config-schema.meta.schema.json": ("config-schema.meta.schema.json", "application/schema+json"),
}


def validate(validator, value, label):
    try:
        validator.validate(value)
    except ValidationError as error:
        raise InputError(f"{label} {error.json_path}：{error.message}") from error


def validate_schema(schema):
    validate(META_VALIDATOR, schema, "Config Schema")
    properties = schema["properties"]
    for name in schema.get("required", []):
        if name not in properties:
            raise InputError(f"required 引用了未宣告的欄位 {name}。")
    for name, definition in properties.items():
        if "default" in definition:
            validate(Draft202012Validator(definition), definition["default"], f"{name}.default")


def validate_provider(raw):
    require_object(raw, "System Description")
    name = required_text(raw.get("system_name"), "System 名稱")
    schema = raw.get("config_schema")
    validate_schema(schema)
    apis = validate_apis(raw.get("apis"))
    return {"system_name": name, "apis": apis, "config_schema": schema}


def route_config(system):
    config = {
        key: system[key] for key in ("system_id", "system_name", "workspace_id", "provider_id", "parameters")
    }
    config["apis"] = system["provider"]["apis"]
    return config


class BuilderServer(ThreadingHTTPServer):
    def __init__(self, port, router_url):
        super().__init__(("127.0.0.1", port), Handler)
        self.lock = threading.Lock()
        self.router_url = router_url
        self.demo_lock = threading.Lock()
        self.demo_registered = False
        self.updating = set()
        demo = json.loads((ROOT / "demo-provider.json").read_text(encoding="utf-8"))
        self.origin = f"http://127.0.0.1:{self.server_port}"
        for api in demo["apis"].values():
            api["url"] = self.origin + urlsplit(api["url"]).path
        demo["id"] = "demo"
        self.demo_template = demo
        mock = validate_provider(json.loads((ROOT / "mock-provider.json").read_text(encoding="utf-8")))
        mock["id"] = "mock-retrieval"
        self.providers = {"demo": demo, mock["id"]: mock}
        parameters = {name: field["default"] for name, field in demo["config_schema"]["properties"].items()}
        system_id = "00000000-0000-4000-8000-000000000001"
        self.demo_system_id = system_id
        self.systems = {system_id: {
            "system_id": system_id,
            "system_name": "產品文件測試",
            "workspace_id": "customer-support",
            "provider_id": "demo",
            "provider": demo,
            "parameters": parameters,
        }}
        self.documents = {system_id: {"warranty-01": "產品保固一年，購買日起算。"}}

    def catalog(self):
        self.ensure_demo_route()
        with self.lock:
            return {
                "workspaces": [{"id": key, "name": name} for key, name in WORKSPACES.items()],
                "providers": list(self.providers.values()),
                "demo_template": self.demo_template,
                "systems": list(self.systems.values()),
            }

    def create_provider(self, raw):
        provider = validate_provider(raw)
        provider["id"] = str(uuid.uuid4())
        with self.lock:
            self.providers[provider["id"]] = provider
        return as_json(201, provider)

    def update_provider(self, provider_id, raw):
        provider = {**validate_provider(raw), "id": provider_id}
        with self.lock:
            if provider_id not in self.providers:
                return router_error(404, "找不到指定的 Provider Template。")
            self.providers[provider_id] = provider
        return as_json(200, provider)

    def create_system(self, raw):
        require_object(raw, "System")
        name = required_text(raw.get("system_name"), "System 名稱")
        provider_id = required_text(raw.get("provider_id"), "Provider")
        workspace_id = raw.get("workspace_id", "customer-support")
        if not isinstance(workspace_id, str) or workspace_id not in WORKSPACES:
            raise InputError("找不到指定的 Workspace。")
        with self.lock:
            provider = self.providers.get(provider_id)
        if provider is None:
            raise InputError("找不到指定的 Provider。")
        parameters = require_object(raw.get("parameters"), "parameters")
        system = {
            "system_id": str(uuid.uuid4()), "system_name": name,
            "workspace_id": workspace_id, "provider_id": provider_id,
            "provider": provider, "parameters": parameters,
        }
        return self.publish_system(system, 201)

    def update_system(self, system_id, raw):
        require_object(raw, "System")
        name = required_text(raw.get("system_name"), "System 名稱")
        parameters = require_object(raw.get("parameters"), "parameters")
        with self.lock:
            current = self.systems.get(system_id)
            if current is None:
                return router_error(404, "找不到已啟用的 System。")
            if system_id in self.updating:
                return as_json(409, {"error": "System 正在處理請求或套用設定，請稍後再試。"})
            candidate = {**current, "system_name": name, "parameters": parameters}
            self.updating.add(system_id)
        try:
            return self.publish_system(candidate, 200)
        finally:
            with self.lock:
                self.updating.remove(system_id)

    def register_route(self, system):
        return exchange(
            self.router_url + "/internal/systems/" + system["system_id"],
            route_config(system), {}, method="PUT", upstream="Route Service", timeout=20,
        )

    def ensure_demo_route(self):
        with self.demo_lock:
            if self.demo_registered:
                return
            with self.lock:
                system = self.systems[self.demo_system_id]
            try:
                self.demo_registered = self.register_route(system).status == 204
            except UpstreamError:
                # The UI and Provider catalog can load before the local Router starts.
                pass

    def publish_system(self, system, status):
        schema = {**system["provider"]["config_schema"], "additionalProperties": False}
        validate(Draft202012Validator(schema), system["parameters"], "System 設定")
        reply = self.register_route(system)
        if reply.status != 204:
            return reply
        with self.lock:
            self.systems[system["system_id"]] = system
        return as_json(status, system)

    def export_system(self, system_id):
        with self.lock:
            system = self.systems.get(system_id)
        if system is None:
            return router_error(404, "找不到已啟用的 System。")
        body = yaml.safe_dump(route_config(system), allow_unicode=True, sort_keys=False).encode()
        return Reply(200, body, {
            "Content-Type": "application/yaml; charset=utf-8",
            "Content-Disposition": f'attachment; filename="retrieval-system-{system_id}.yaml"',
        })

    def forward(self, path, system_id, operation, payload, request_headers):
        if system_id == self.demo_system_id:
            self.ensure_demo_route()
        headers = {}
        with self.lock:
            system = self.systems.get(system_id)
        if system and (auth := system["provider"]["apis"][operation]["auth"]):
            if (value := request_headers.get(auth["header"])) is not None:
                headers[auth["header"]] = value
        return exchange(self.router_url + path, payload, headers, upstream="Route Service", timeout=20)

    def demo_request(self, operation, raw, headers):
        require_object(raw, "Provider Request")
        system_id = required_text(raw.get("system_id"), "system_id")
        parameters = require_object(raw.get("parameters"), "parameters")
        if operation == "init":
            if headers.get("Authorization") != DEMO_INIT_AUTH:
                return Reply(401, b"", {"WWW-Authenticate": "Bearer"})
            with self.lock:
                self.documents.setdefault(system_id, {})
            return Reply(204, b"", {})
        if headers.get("Authorization") != "Bearer demo-token":
            reply = as_json(401, {"error": "示範 Provider 需要 Bearer demo-token。"})
            return Reply(reply.status, reply.body, {**reply.headers, "WWW-Authenticate": "Bearer"})
        payload = require_object(raw.get("payload"), "payload")
        with self.lock:
            documents = self.documents.get(system_id)
            if documents is None:
                return as_json(404, {"error": "示範 Provider 尚未初始化此 System。"})
            if operation == "inference":
                query = required_text(payload.get("query"), "query")
                limit = parameters.get("top_k", 5)
                if not Draft202012Validator({"type": "integer"}).is_valid(limit):
                    raise InputError("示範 Provider 的 top_k 必須是整數。")
                limit = max(0, int(limit))
                query_terms = [query[i:i + 2] for i in range(len(query) - 1)]
                matching = [
                    {"document_id": doc_id, **({"text": value} if parameters.get("include_text", True) else {})}
                    for doc_id, value in documents.items()
                    if query.casefold() in value.casefold() or any(term in value for term in query_terms)
                ]
                return as_json(200, {"query": query, "results": matching[:limit]})
            action = payload.get("action")
            if action == "list":
                return as_json(200, {"documents": list(documents)})
            if action == "upsert":
                doc_id = required_text(payload.get("document_id"), "document_id")
                documents[doc_id] = required_text(payload.get("text"), "text")
                return as_json(200, {"document_id": doc_id, "status": "indexed"})
            if action == "delete":
                doc_id = required_text(payload.get("document_id"), "document_id")
                return as_json(200, {"document_id": doc_id, "deleted": documents.pop(doc_id, None) is not None})
            raise InputError("可用的示範 action 為 upsert、list、delete。")


class Handler(JsonHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/catalog":
            reply = as_json(200, self.server.catalog())
        elif route := SYSTEM_EXPORT_ROUTE.fullmatch(path):
            reply = self.server.export_system(route[1])
        elif path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            reply = Reply(200, (ROOT / filename).read_bytes(), {"Content-Type": content_type})
        else:
            reply = router_error(404, "找不到路徑。")
        self.write_reply(reply)

    def dispatch(self, path, body):
        if path == "/api/providers":
            return self.server.create_provider(body)
        if path == "/api/systems":
            return self.server.create_system(body)
        if path == "/api/schema/validate":
            validate_schema(body)
            return as_json(200, {"valid": True})
        if route := SYSTEM_ROUTE.fullmatch(path):
            return self.server.forward(path, *route.groups(), body, self.headers)
        if path.removeprefix("/demo/") in OPERATIONS and path.startswith("/demo/"):
            return self.server.demo_request(path.removeprefix("/demo/"), body, self.headers)
        return router_error(404, "找不到操作路徑。")

    def replace(self, path, body):
        if route := SYSTEM_CONFIG_ROUTE.fullmatch(path):
            return self.server.update_system(route[1], body)
        if route := PROVIDER_CONFIG_ROUTE.fullmatch(path):
            return self.server.update_provider(route[1], body)
        return router_error(404, "找不到操作路徑。")

    def do_POST(self):
        self.handle_json(self.dispatch)

    def do_PUT(self):
        self.handle_json(self.replace)


def build_frontend():
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("建置 React 前端需要 Node.js 和 npm。")
    if not (ROOT / "node_modules" / ".package-lock.json").is_file():
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=ROOT, check=True)
    subprocess.run([npm, "run", "build"], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--router-url", default="http://127.0.0.1:8767")
    parser.add_argument("--skip-build", action="store_true", help="使用事先建置的 React 檔案")
    args = parser.parse_args()
    try:
        if not args.skip_build:
            build_frontend()
        if not (ROOT / "dist" / "app.js").is_file():
            parser.error("找不到 dist/app.js，請先建置 React 前端。")
    except (RuntimeError, subprocess.CalledProcessError) as error:
        parser.error(f"React 前端建置失敗：{error}")
    with BuilderServer(args.port, args.router_url.rstrip("/")) as server:
        print(f"Retrieval Builder · {server.origin}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
