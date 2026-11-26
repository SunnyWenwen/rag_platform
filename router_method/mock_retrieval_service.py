"""Start a standalone mock Retrieval Provider."""

import argparse
from http.server import ThreadingHTTPServer
from threading import Lock

from provider_http import JsonHandler, as_json, provider_request


RESPONSES = {
    "init": "成功呼叫init",
    "ingestion": "成功呼叫ingestion",
    "inference": "成功呼叫inference",
}


class MockRetrievalHandler(JsonHandler):
    def do_POST(self):
        self.handle_json(self.dispatch, same_origin=False)

    def dispatch(self, path, body):
        operation = path.removeprefix("/")
        if operation not in RESPONSES:
            return as_json(404, {"error": "找不到 Mock API。"})
        system_id = provider_request(operation, body)
        with self.server.lock:
            if operation == "init":
                self.server.parameters[system_id] = body["parameters"]
            elif system_id not in self.server.parameters:
                return as_json(404, {"error": "Mock Provider 尚未初始化此 System。"})
        return as_json(200, {"message": RESPONSES[operation], "see payload": body})


class MockServer(ThreadingHTTPServer):
    def __init__(self, port):
        super().__init__(("127.0.0.1", port), MockRetrievalHandler)
        self.lock = Lock()
        self.parameters = {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    with MockServer(args.port) as server:
        print(f"Mock Retrieval Service · http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
