"""Run the Retrieval Router MVP with an embedded demonstration Provider."""

import argparse
import json
import os
import re
import socket
import threading
import uuid
from collections import Counter
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parent
OPERATIONS = ("init", "ingestion", "inference")
DEMO_INIT_AUTH = "Bearer demo-init-token"
WORKSPACES = {
    "customer-support": "Customer Support",
    "engineering": "Engineering",
    "operations": "Operations",
}
MAX_REQUEST_BYTES = 2_000_000
META_SCHEMA = json.loads((ROOT / "config-schema.meta.schema.json").read_text())
META_VALIDATOR = Draft202012Validator(META_SCHEMA)
SYSTEM_ROUTE = re.compile(r"/systems/([a-f0-9-]{36})/(ingestion|inference)")
SYSTEM_CONFIG_ROUTE = re.compile(r"/api/systems/([a-f0-9-]{36})")
SYSTEM_EXPORT_ROUTE = re.compile(r"/api/systems/([a-f0-9-]{36})/export")
PROVIDER_CONFIG_ROUTE = re.compile(r"/api/providers/(demo|[a-f0-9-]{36})")
HEADER_NAME = re.compile(r"[A-Za-z][A-Za-z0-9!#$%&'*+.^_\x60|~-]*")
RESERVED_HEADERS = {
    "connection", "content-encoding", "content-length", "content-type", "cookie",
    "expect", "host", "origin", "proxy-authorization", "transfer-encoding",
}
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/config-schema.meta.schema.json": ("config-schema.meta.schema.json", "application/schema+json"),
}
PROVIDER_RESPONSE_HEADERS = (
    "Content-Type", "Content-Encoding", "Content-Language", "Retry-After", "WWW-Authenticate",
)


class InputError(ValueError):
    pass


class UpstreamError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(NoRedirect())


@dataclass(frozen=True)
class Reply:
    status: int
    body: bytes
    headers: dict[str, str]


def as_json(status, value):
    return Reply(status, json.dumps(value, ensure_ascii=False).encode(), {
        "Content-Type": "application/json; charset=utf-8"
    })


def require_object(value, label):
    if not isinstance(value, dict):
        raise InputError(f"{label} 必須是 JSON object。")
    return value


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"請填寫 {label}。")
    return value.strip()


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
    endpoints = require_object(raw.get("apis"), "apis")
    apis = {}
    for operation in OPERATIONS:
        endpoint = require_object(endpoints.get(operation), operation)
        url = required_text(endpoint.get("url"), f"{operation} URL")
        try:
            address = urlsplit(url)
            address.port
        except ValueError as error:
            raise InputError(f"{operation} URL 格式有誤。") from error
        if (address.scheme not in {"http", "https"} or not address.hostname
                or address.username is not None or address.fragment or any(ch.isspace() for ch in url)):
            raise InputError(f"{operation} URL 請使用完整的 HTTP 或 HTTPS URL。")
        auth = endpoint.get("auth")
        if auth is not None:
            require_object(auth, f"{operation} Auth")
            header = required_text(auth.get("header"), f"{operation} Auth Header")
            if not HEADER_NAME.fullmatch(header) or header.lower() in RESERVED_HEADERS:
                raise InputError(f"{operation} Auth Header 名稱不可用。")
            if operation == "init":
                auth = {"header": header, "secret_ref": required_text(auth.get("secret_ref"), "Init Secret 環境變數")}
            else:
                auth = {"header": header, "scheme": str(auth.get("scheme", "")).strip()}
        apis[operation] = {"url": url, "auth": auth}
        if operation != "init":
            apis[operation]["description"] = required_text(endpoint.get("description"), f"{operation} 使用說明")
            if "sample" not in endpoint:
                raise InputError(f"請提供 {operation} JSON Sample。")
            apis[operation]["sample"] = endpoint["sample"]
    return {"system_name": name, "apis": apis, "config_schema": schema}


def exchange(url, body, auth_headers):
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode(),
        headers={"Content-Type": "application/json", **auth_headers},
        method="POST",
    )
    try:
        try:
            response = OPENER.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            headers = {name: response.headers[name] for name in PROVIDER_RESPONSE_HEADERS if name in response.headers}
            return Reply(response.status, response.read(), headers)
    except (URLError, socket.timeout, OSError, ValueError) as error:
        raise UpstreamError("無法取得 Provider 回應，請確認服務 URL 與連線。") from error


class PrototypeServer(ThreadingHTTPServer):
    def __init__(self, port):
        super().__init__(("127.0.0.1", port), Handler)
        self.lock = threading.Lock()
        self.active_requests = Counter()
        self.updating = set()
        demo = json.loads((ROOT / "demo-provider.json").read_text())
        self.origin = f"http://127.0.0.1:{self.server_port}"
        for api in demo["apis"].values():
            api["url"] = self.origin + urlsplit(api["url"]).path
        demo["id"] = "demo"
        self.demo_template = demo
        self.providers = {"demo": demo}
        parameters = {name: field["default"] for name, field in demo["config_schema"]["properties"].items()}
        system_id = "00000000-0000-4000-8000-000000000001"
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
                return as_json(404, {"error": "找不到指定的 Provider Template。"})
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
                return as_json(404, {"error": "找不到已啟用的 System。"})
            if system_id in self.updating or self.active_requests[system_id]:
                return as_json(409, {"error": "System 正在處理請求或套用設定，請稍後再試。"})
            candidate = {**current, "system_name": name, "parameters": parameters}
            self.updating.add(system_id)
        try:
            return self.publish_system(candidate, 200)
        finally:
            with self.lock:
                self.updating.remove(system_id)

    def publish_system(self, system, status):
        system_id = system["system_id"]
        provider = system["provider"]
        parameters = system["parameters"]
        schema = {**provider["config_schema"], "additionalProperties": False}
        validate(Draft202012Validator(schema), parameters, "System 設定")
        endpoint = provider["apis"]["init"]
        headers = {}
        if auth := endpoint["auth"]:
            demo_init = self.demo_template["apis"]["init"]
            # The built-in credential applies only to the embedded demo endpoint.
            secret = DEMO_INIT_AUTH if endpoint == demo_init else os.environ.get(auth["secret_ref"])
            if not secret:
                raise InputError(f"尚未設定 Init 憑證環境變數 {auth['secret_ref']}。")
            headers[auth["header"]] = secret
        reply = exchange(endpoint["url"], {
            "system_id": system_id, "parameters": parameters, "payload": None
        }, headers)
        if reply.status not in {200, 204}:
            return as_json(502, {
                "error": f"Provider Init 回傳 HTTP {reply.status}，設定未生效。"
            })
        with self.lock:
            self.systems[system_id] = system
        return as_json(status, system)

    def export_system(self, system_id):
        with self.lock:
            system = self.systems.get(system_id)
        if system is None:
            return as_json(404, {"error": "找不到已啟用的 System。"})
        config = {
            key: system[key] for key in ("system_id", "system_name", "workspace_id", "provider_id", "parameters")
        }
        config["apis"] = system["provider"]["apis"]
        body = yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode()
        return Reply(200, body, {
            "Content-Type": "application/yaml; charset=utf-8",
            "Content-Disposition": f'attachment; filename="retrieval-system-{system_id}.yaml"',
        })

    def forward(self, system_id, operation, payload, request_headers):
        with self.lock:
            system = self.systems.get(system_id)
            if system is None:
                return as_json(404, {"error": "找不到已啟用的 System。"})
            if system_id in self.updating:
                return as_json(409, {"error": "System 正在套用設定，請稍後再試。"})
            endpoint = system["provider"]["apis"][operation]
            self.active_requests[system_id] += 1
        try:
            headers = {}
            if auth := endpoint["auth"]:
                if (value := request_headers.get(auth["header"])) is not None:
                    headers[auth["header"]] = value
            return exchange(endpoint["url"], {
                "system_id": system_id, "parameters": system["parameters"], "payload": payload
            }, headers)
        finally:
            with self.lock:
                self.active_requests[system_id] -= 1
                if not self.active_requests[system_id]:
                    del self.active_requests[system_id]

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


def reject_json_constant(value):
    raise ValueError(f"{value} 不是有效的 JSON 值。")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep credentials and request contents out of access logs.
        return

    def read_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST_BYTES:
                raise ValueError("JSON Body 大小超出允許範圍。")
            return json.loads(self.rfile.read(size), parse_constant=reject_json_constant)
        except (ValueError, RecursionError) as error:
            raise InputError(f"JSON Body 無效。{error}") from error

    def write_reply(self, reply):
        self.send_response(reply.status)
        for name, value in reply.headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(reply.body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(reply.body)

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
            reply = as_json(404, {"error": "找不到路徑。"})
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
            return self.server.forward(*route.groups(), body, self.headers)
        if path.removeprefix("/demo/") in OPERATIONS and path.startswith("/demo/"):
            return self.server.demo_request(path.removeprefix("/demo/"), body, self.headers)
        return as_json(404, {"error": "找不到操作路徑。"})

    def replace(self, path, body):
        if route := SYSTEM_CONFIG_ROUTE.fullmatch(path):
            return self.server.update_system(route[1], body)
        if route := PROVIDER_CONFIG_ROUTE.fullmatch(path):
            return self.server.update_provider(route[1], body)
        return as_json(404, {"error": "找不到操作路徑。"})

    def handle_json(self, action):
        path = urlsplit(self.path).path
        allowed_origins = {self.server.origin, f"http://localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        if origin is not None and origin not in allowed_origins:
            self.write_reply(as_json(403, {"error": "此 MVP 只接受同源瀏覽器請求。"}))
            return
        try:
            reply = action(path, self.read_json())
        except InputError as error:
            reply = as_json(400, {"error": str(error)})
        except UpstreamError as error:
            reply = as_json(502, {"error": str(error)})
        self.write_reply(reply)

    def do_POST(self):
        self.handle_json(self.dispatch)

    def do_PUT(self):
        self.handle_json(self.replace)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with PrototypeServer(args.port) as server:
        print(f"Retrieval Router MVP · {server.origin}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
