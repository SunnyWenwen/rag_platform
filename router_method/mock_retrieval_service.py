"""Start a standalone mock Retrieval Provider."""

import argparse
import json
import os
from http.server import ThreadingHTTPServer
from threading import Lock

from provider_http import (
    MOCK_INIT_AUTH, MOCK_INIT_SECRET_REF, MOCK_REQUEST_AUTH, InputError, ProviderCorsHandler,
    as_json, provider_request, required_text,
)


RESPONSES = {
    "init": "成功呼叫init",
    "ingestion": "成功呼叫ingestion",
    "inference": "成功呼叫inference",
}
DEFAULT_BUILDER_ORIGINS = {"http://127.0.0.1:8765", "http://localhost:8765"}
CREDENTIAL_HEADERS = {"authorization", "proxy-authorization", "cookie", "x-api-key"}


class MockRetrievalHandler(ProviderCorsHandler):
    browser_provider_paths = frozenset({"/ingestion", "/inference"})

    def read_request_body(self, size):
        body = super().read_request_body(size)
        self.request_body = body
        return body

    def write_reply(self, reply):
        headers = [
            [name, "[redacted]" if name.lower() in CREDENTIAL_HEADERS else value]
            for name, value in self.headers.items()
        ]
        entry = {
            "method": self.command,
            "url": self.path,
            "request_headers": headers,
            "request_body": getattr(self, "request_body", b"").decode("utf-8", errors="replace"),
            "status": reply.status,
            "response_body": reply.body.decode("utf-8", errors="replace"),
        }
        print("[Mock Provider] " + json.dumps(entry, ensure_ascii=False, indent=2), flush=True)
        super().write_reply(reply)

    def do_POST(self):
        self.handle_json(self.dispatch, same_origin=False)

    def dispatch(self, path, body):
        operation = path.removeprefix("/")
        if operation not in RESPONSES:
            return as_json(404, {"error": "找不到 Mock API。"})
        expected = self.server.init_auth if operation == "init" else MOCK_REQUEST_AUTH
        if self.headers.get("Authorization") != expected:
            return as_json(401, {"error": "Mock Provider 需要有效的 Authorization。"},
                           headers={"WWW-Authenticate": "Bearer"})

        system_id = provider_request(operation, body)
        with self.server.lock:
            if operation == "init":
                parameters = body["parameters"]
                if parameters.keys() != {"domain_name"}:
                    raise InputError("Mock Init 需要 domain_name 參數。")
                required_text(parameters["domain_name"], "domain_name")
                self.server.parameters[system_id] = parameters
            elif system_id not in self.server.parameters:
                return as_json(404, {"error": "Mock Provider 尚未初始化此 System。"})
            domain_name = self.server.parameters[system_id]["domain_name"]
        return as_json(200, {"message": RESPONSES[operation], "domain_name": domain_name, "see payload": body})


class MockServer(ThreadingHTTPServer):
    def __init__(self, port, builder_origins=()):
        super().__init__(("127.0.0.1", port), MockRetrievalHandler)
        self.lock = Lock()
        self.parameters = {}
        self.init_auth = os.environ.get(MOCK_INIT_SECRET_REF, MOCK_INIT_AUTH)
        if not self.init_auth:
            self.server_close()
            raise ValueError(f"{MOCK_INIT_SECRET_REF} 不可為空白。")
        self.provider_origins = DEFAULT_BUILDER_ORIGINS.union(builder_origins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--builder-origin", action="append", default=[], help="額外允許的 Builder UI Origin，可重複指定")
    args = parser.parse_args()
    try:
        server = MockServer(args.port, args.builder_origin)
    except ValueError as error:
        parser.error(str(error))
    with server:
        print(f"Mock Retrieval Service · http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
