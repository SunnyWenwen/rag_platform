"""Run a standalone Route Service for Provider-backed Retrieval Systems."""

import argparse
import json
import os
import re
import threading
from collections import Counter
from dataclasses import dataclass
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml


OPERATIONS = ("init", "ingestion", "inference")
DEMO_INIT_AUTH = "Bearer demo-init-token"
MAX_REQUEST_BYTES = 2_000_000
SYSTEM_ID_PATTERN = r"[a-f0-9-]{36}"
SYSTEM_ROUTE = re.compile(r"/systems/(" + SYSTEM_ID_PATTERN + r")/(ingestion|inference)")
PUBLISH_ROUTE = re.compile(r"/internal/systems/(" + SYSTEM_ID_PATTERN + r")")
HEADER_NAME = re.compile(r"[A-Za-z][A-Za-z0-9!#$%&'*+.^_\x60|~-]*")
RESERVED_HEADERS = {
    "connection", "content-encoding", "content-length", "content-type", "cookie",
    "expect", "host", "origin", "proxy-authorization", "transfer-encoding",
}
PROVIDER_RESPONSE_HEADERS = (
    "Content-Type", "Content-Encoding", "Content-Language", "Retry-After", "WWW-Authenticate",
)
RESPONSE_SOURCE_HEADER = "Retrieval-Response-Source"


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


def as_json(status, value, *, headers=None):
    return Reply(status, json.dumps(value, ensure_ascii=False).encode(), {
        "Content-Type": "application/json; charset=utf-8",
        **(headers or {}),
    })


def router_error(status, message):
    return as_json(status, {"error": message}, headers={RESPONSE_SOURCE_HEADER: "router"})


def require_object(value, label):
    if not isinstance(value, dict):
        raise InputError(f"{label} 必須是 JSON object。")
    return value


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"請填寫 {label}。")
    return value.strip()


def validate_apis(value):
    endpoints = require_object(value, "apis")
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
    return apis


def exchange(url, body, auth_headers, *, method="POST", source=None, upstream="Provider", timeout=15):
    try:
        request = Request(
            url,
            data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode(),
            headers={"Content-Type": "application/json", **auth_headers},
            method=method,
        )
        try:
            response = OPENER.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            headers = {name: response.headers[name] for name in PROVIDER_RESPONSE_HEADERS if name in response.headers}
            if source == "provider":
                headers[RESPONSE_SOURCE_HEADER] = source
            elif RESPONSE_SOURCE_HEADER in response.headers:
                headers[RESPONSE_SOURCE_HEADER] = response.headers[RESPONSE_SOURCE_HEADER]
            return Reply(response.status, response.read(), headers)
    except (URLError, OSError, ValueError, HTTPException) as error:
        raise UpstreamError(f"無法取得 {upstream} 回應，請確認服務 URL 與連線。") from error


class RouterServer(ThreadingHTTPServer):
    def __init__(self, host, port, enable_builder=False):
        super().__init__((host, port), RouterHandler)
        self.origin = f"http://{host}:{self.server_port}"
        self.enable_builder = enable_builder
        self.lock = threading.Lock()
        self.systems = {}
        self.active_requests = Counter()
        self.updating = set()

    def publish(self, system_id, raw, *, local_builder=False):
        require_object(raw, "Router 設定")
        parameters = require_object(raw.get("parameters"), "parameters")
        apis = validate_apis(raw.get("apis"))
        endpoint = apis["init"]
        headers = {}
        if auth := endpoint["auth"]:
            secret = os.environ.get(auth["secret_ref"])
            address = urlsplit(endpoint["url"])
            if (
                local_builder and auth == {"header": "Authorization", "secret_ref": "ROUTER_DEMO_INIT_AUTH"}
                and address.hostname == "127.0.0.1" and address.path == "/demo/init"
            ):
                secret = DEMO_INIT_AUTH
            if not secret:
                raise InputError(f"尚未設定 Init 憑證環境變數 {auth['secret_ref']}。")
            headers[auth["header"]] = secret

        with self.lock:
            if system_id in self.updating or self.active_requests[system_id]:
                return as_json(409, {"error": "System 正在處理請求或套用設定，請稍後再試。"})
            self.updating.add(system_id)
        try:
            reply = exchange(endpoint["url"], {
                "system_id": system_id, "parameters": parameters, "payload": None,
            }, headers, source="provider")
            if reply.status not in {200, 204}:
                return router_error(502, f"Provider Init 回傳 HTTP {reply.status}，設定未生效。")
            with self.lock:
                self.systems[system_id] = {"parameters": parameters, "apis": apis}
            return Reply(204, b"", {})
        finally:
            with self.lock:
                self.updating.remove(system_id)

    def forward(self, system_id, operation, payload, request_headers):
        with self.lock:
            system = self.systems.get(system_id)
            if system is None:
                return router_error(404, "找不到已啟用的 System。")
            if system_id in self.updating:
                return as_json(409, {"error": "System 正在套用設定，請稍後再試。"})
            endpoint = system["apis"][operation]
            self.active_requests[system_id] += 1
        try:
            headers = {}
            if auth := endpoint["auth"]:
                if (value := request_headers.get(auth["header"])) is not None:
                    headers[auth["header"]] = value
            return exchange(endpoint["url"], {
                "system_id": system_id, "parameters": system["parameters"], "payload": payload
            }, headers, source="provider")
        finally:
            with self.lock:
                self.active_requests[system_id] -= 1
                if not self.active_requests[system_id]:
                    del self.active_requests[system_id]

def reject_json_constant(value):
    raise ValueError(f"{value} 不是有效的 JSON 值。")


class JsonHandler(BaseHTTPRequestHandler):
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
            reply = router_error(400, str(error))
        except UpstreamError as error:
            reply = router_error(502, str(error))
        self.write_reply(reply)

class RouterHandler(JsonHandler):
    def do_GET(self):
        if urlsplit(self.path).path == "/health":
            self.write_reply(as_json(200, {"status": "ok"}))
        else:
            self.write_reply(router_error(404, "找不到路徑。"))

    def do_POST(self):
        route = SYSTEM_ROUTE.fullmatch(urlsplit(self.path).path)
        if route is None:
            self.write_reply(router_error(404, "找不到操作路徑。"))
            return
        self.handle_json(lambda path, body: self.server.forward(*route.groups(), body, self.headers))

    def do_PUT(self):
        route = PUBLISH_ROUTE.fullmatch(urlsplit(self.path).path)
        if route is None or not self.server.enable_builder:
            self.write_reply(router_error(404, "找不到操作路徑。"))
            return
        local_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Origin") is not None or self.headers.get("Host") not in local_hosts:
            self.write_reply(router_error(403, "Builder 管理入口只接受本機後端呼叫。"))
            return
        self.handle_json(lambda path, body: self.server.publish(route[1], body, local_builder=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--enable-builder", action="store_true", help="允許同機的 Builder 更新路由")
    parser.add_argument("--config", action="append", type=Path, default=[], help="載入 Builder 匯出的 YAML，可重複指定")
    args = parser.parse_args()
    if args.enable_builder and args.host != "127.0.0.1":
        parser.error("--enable-builder 只支援 127.0.0.1。")
    with RouterServer(args.host, args.port, args.enable_builder) as server:
        for path in args.config:
            try:
                config = require_object(yaml.safe_load(path.read_text(encoding="utf-8")), "Router 設定")
                system_id = required_text(config.get("system_id"), "System ID")
                if not re.fullmatch(SYSTEM_ID_PATTERN, system_id):
                    raise InputError("System ID 格式有誤。")
                if system_id in server.systems:
                    raise InputError("System ID 重複。")
                reply = server.publish(system_id, config)
                if reply.status != 204:
                    raise InputError(json.loads(reply.body)["error"])
            except (OSError, yaml.YAMLError, InputError, UpstreamError) as error:
                parser.error(f"{path}：{error}")
        print(f"Retrieval Route Service · {server.origin}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
