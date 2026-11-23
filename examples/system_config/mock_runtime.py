"""Run a fixture-backed DEV Runtime on the local loopback interface."""

import argparse
from base64 import b64encode
from hmac import compare_digest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

HERE = Path(__file__).resolve().parent
SCENARIO_FILE = HERE / "runtime_http.examples.json"
MOCK_CREDENTIALS = {
    "runtimeManagementBasic": "mock:mock",
    "systemIngestionBasic": "ingestion:mock-ingestion",
    "systemInferenceBasic": "inference:mock-inference",
}
CHALLENGE = 'Basic realm="retrieval-runtime"'
NO_BODY = object()
PROBE_PATHS = {"/health/live", "/health/ready", "/internal/v1/catalog"}


def load_scenarios(system_id=None):
    source = SCENARIO_FILE.read_text(encoding="utf-8")
    scenarios = json.loads(source)["scenarios"]
    if system_id is None:
        return scenarios
    parsed = UUID(system_id)
    if parsed.version != 4 or str(parsed) != system_id:
        raise ValueError("System ID must be a lowercase UUIDv4")
    initialize = next(step for step in scenarios["happy_path"] if step["request"]["method"] == "PUT")
    fixture_id = initialize["response"]["body"]["system_id"]
    return json.loads(source.replace(fixture_id, system_id))["scenarios"]


def fixture_body(message):
    if "body_file" in message:
        return json.loads((HERE / message["body_file"]).read_text(encoding="utf-8"))
    return message.get("body")


def normalized_target(target):
    url = urlsplit(target)
    return url.path, tuple(sorted(parse_qsl(url.query, keep_blank_values=True)))


def mock_auth_scheme(target):
    path = urlsplit(target).path
    if path.startswith("/internal/systems/"):
        if path.endswith("/v1/queries"):
            return "systemInferenceBasic"
        return "systemIngestionBasic"
    return "runtimeManagementBasic"


def request_matches(expected, method, target, headers, body):
    expected_body = fixture_body(expected) if {"body_file", "body"} & expected.keys() else NO_BODY
    return (
        expected["method"] == method
        and normalized_target(expected["path"]) == normalized_target(target)
        and all(headers.get(name.lower()) == value for name, value in expected.get("headers", {}).items())
        and expected_body == body
    )


def is_poll_path(path):
    return path.endswith("/ingestion-status") or "/v1/ingestions/" in path and not path.endswith("/cancel")


class ScenarioReplay:
    def __init__(self, scenarios, scenario):
        self.scenarios = scenarios
        self.probes = {
            step["request"]["path"]: step["response"]
            for step in scenarios["happy_path"]
            if step["request"]["method"] == "GET" and step["request"]["path"] in PROBE_PATHS
        }
        self.lock = Lock()
        self.reset(scenario)

    def reset(self, scenario=None):
        self.name = scenario if scenario is not None else self.name
        self.steps = self.scenarios[self.name]
        self.position = 0
        self.poll_results = {}

    def handle(self, method, target, headers, body):
        with self.lock:
            if (method, target) == ("POST", "/__mock/reset"):
                scenario = body.get("scenario") if isinstance(body, dict) else None
                if body is not NO_BODY and (not isinstance(scenario, str) or scenario not in self.scenarios):
                    return self.problem(400, "MOCK_SCENARIO_INVALID", "Choose a scenario from --list.")
                self.reset(scenario)
                return {"status": 204}

            path, query = normalized_target(target)
            probe = method == "GET" and not query and body is NO_BODY and path in self.probes
            candidate = self.position
            while candidate < len(self.steps):
                step = self.steps[candidate]
                expected = step["request"]
                if request_matches(expected, method, target, headers, body):
                    self.position = candidate + 1
                    response = step["response"]
                    if method == "GET" and is_poll_path(path):
                        self.poll_results[(path, query)] = response
                    return response
                if probe or expected["method"] != "GET" or expected["path"] not in self.probes:
                    break
                candidate += 1

            if probe:
                return self.probes[path]
            if method == "GET" and body is NO_BODY and (path, query) in self.poll_results:
                return self.poll_results[(path, query)]
            if self.position == len(self.steps):
                message = f"{self.name} is complete. Reset the scenario before replaying it."
            else:
                expected = self.steps[self.position]["request"]
                message = (
                    f"{self.name} step {self.position + 1} expects "
                    f"{expected['method']} {expected['path']} with the fixture body and headers."
                )
            return self.problem(409, "MOCK_STEP_MISMATCH", message)

    @staticmethod
    def problem(status, code, message, **headers):
        return {
            "status": status,
            "headers": headers,
            "body": {"error": {"code": code, "message": message, "module": None}},
        }


class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle_request(self):
        authorization = self.headers.get("Authorization", "")
        credentials = MOCK_CREDENTIALS[mock_auth_scheme(self.path)]
        expected = b"Basic " + b64encode(credentials.encode())
        if not compare_digest(authorization.encode(), expected):
            self.close_connection = True
            response = ScenarioReplay.problem(
                401, "UNAUTHENTICATED", "Mock Runtime credentials are missing or invalid.",
                **{"WWW-Authenticate": CHALLENGE},
            )
        else:
            body, response = self.read_json()
            if response is None:
                response = self.server.replay.handle(
                    self.command, self.path,
                    {name.lower(): value for name, value in self.headers.items()}, body,
                )
        self.write_response(response)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or self.headers.get("Transfer-Encoding") is not None:
                raise ValueError
        except ValueError:
            self.close_connection = True
            return None, ScenarioReplay.problem(400, "INVALID_JSON", "Expected a fixed-length JSON body.")
        if not length:
            return NO_BODY, None
        if self.headers.get_content_type() != "application/json":
            self.close_connection = True
            return None, ScenarioReplay.problem(415, "UNSUPPORTED_MEDIA_TYPE", "Expected application/json.")
        try:
            return json.loads(self.rfile.read(length)), None
        except (UnicodeError, ValueError):
            return None, ScenarioReplay.problem(400, "INVALID_JSON", "Invalid JSON request body.")

    def write_response(self, response):
        self.send_response(response["status"])
        if self.close_connection:
            self.send_header("Connection", "close")
        for name, value in response.get("headers", {}).items():
            self.send_header(name, value)
        if response["status"] != 204:
            body = json.dumps(fixture_body(response), ensure_ascii=False).encode("utf-8")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        else:
            body = b""
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        # The mock diagnostics identify the expected step without logging credentials or payloads.
        return

    do_GET = do_POST = do_PUT = do_DELETE = handle_request


def create_server(scenarios, scenario, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), MockHandler)
    server.replay = ScenarioReplay(scenarios, scenario)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List the available scenarios")
    parser.add_argument("--scenario", default="happy_path")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--system-id", help="Replace the fixture System ID with this UUIDv4")
    args = parser.parse_args()
    try:
        scenarios = load_scenarios(args.system_id)
    except ValueError as error:
        parser.error(str(error))
    if args.list:
        print("\n".join(scenarios))
        return
    if args.scenario not in scenarios:
        parser.error("Unknown scenario. Use --list for the available scenarios.")
    with create_server(scenarios, args.scenario, args.port) as server:
        print(f"Mock Runtime at http://127.0.0.1:{server.server_port} ({args.scenario})", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
