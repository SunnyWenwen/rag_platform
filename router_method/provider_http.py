"""HTTP helpers for the Builder and its local Provider examples."""

import json
import math
import re
from dataclasses import dataclass
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


OPERATIONS = ("init", "ingestion", "inference")
MAX_REQUEST_BYTES = 2_000_000
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


def builder_error(status, message):
    return as_json(status, {"error": message}, headers={RESPONSE_SOURCE_HEADER: "builder"})


def require_object(value, label):
    if not isinstance(value, dict):
        raise InputError(f"{label} 必須是 JSON object。")
    return value


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"請填寫 {label}。")
    return value.strip()


def provider_request(operation, raw):
    require_object(raw, "Provider Request")
    field = "parameters" if operation == "init" else "payload"
    if raw.keys() != {"system_id", field}:
        raise InputError(f"Provider Request 必須包含 system_id 與 {field}。")
    if operation == "init":
        require_object(raw[field], field)
    return required_text(raw["system_id"], "system_id")


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


def exchange(url, body, auth_headers, *, read_body=True, timeout=15):
    try:
        request = Request(
            url,
            data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode(),
            headers={"Content-Type": "application/json", **auth_headers},
            method="POST",
        )
        try:
            response = OPENER.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            headers = {name: response.headers[name] for name in PROVIDER_RESPONSE_HEADERS if name in response.headers}
            headers[RESPONSE_SOURCE_HEADER] = "provider"
            return Reply(response.status, response.read() if read_body else b"", headers)
    except (URLError, OSError, ValueError, HTTPException) as error:
        raise UpstreamError("無法取得 Provider 回應，請確認服務 URL 與連線。") from error


def reject_json_constant(value):
    raise ValueError(f"{value} 不是有效的 JSON 值。")


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("數字超出允許範圍。")
    return number


class JsonHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep credentials and request contents out of access logs.
        return

    def read_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST_BYTES:
                raise ValueError("JSON Body 大小超出允許範圍。")
            return json.loads(self.rfile.read(size), parse_constant=reject_json_constant, parse_float=finite_float)
        except (ValueError, RecursionError) as error:
            raise InputError(f"JSON Body 無效。{error}") from error

    def write_reply(self, reply):
        self.send_response(reply.status)
        for name, value in reply.headers.items():
            self.send_header(name, value)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(reply.body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(reply.body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_json(self, action, *, same_origin=True):
        path = urlsplit(self.path).path
        if same_origin:
            allowed_origins = {self.server.origin, f"http://localhost:{self.server.server_port}"}
            origin = self.headers.get("Origin")
            if origin is not None and origin not in allowed_origins:
                self.write_reply(builder_error(403, "此 MVP 只接受同源瀏覽器請求。"))
                return
        try:
            reply = action(path, self.read_json())
        except InputError as error:
            reply = builder_error(400, str(error))
        except UpstreamError as error:
            reply = builder_error(502, str(error))
        self.write_reply(reply)
