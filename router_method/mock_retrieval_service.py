"""Start a standalone mock Provider for the Router MVP."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


RESPONSES = {
    "/init": "成功呼叫init",
    "/ingestion": "成功呼叫ingestion",
    "/inference": "成功呼叫inference",
}


class MockRetrievalHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        message = RESPONSES.get(urlsplit(self.path).path)
        if message is None:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0:
                raise ValueError
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        self.rfile.read(length)
        body = message.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), MockRetrievalHandler) as server:
        print(f"Mock Retrieval Service · http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
