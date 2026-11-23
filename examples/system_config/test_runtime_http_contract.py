"""Exercise every Runtime HTTP scenario against the local mock and the bundled OpenAPI."""

from base64 import b64encode
from contextlib import closing
from http.client import HTTPConnection
import json
import re
from threading import Thread
from urllib.parse import parse_qs, unquote, urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from build_runtime_openapi import at_pointer, build_bundle
from mock_runtime import MOCK_CREDENTIALS, create_server, fixture_body, load_scenarios, mock_auth_scheme
from validate_runtime_http_examples import FORMATS, verify


API_ID = "urn:retrieval-builder:dev-http-contract"
METHODS = {"get", "post", "put", "delete"}
MEDIA = "application/json"
TRANSPORT_HEADERS = {"server", "date", "connection", "content-length", "content-type"}


def pointer(*parts):
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


class OpenAPIContract:
    def __init__(self):
        self.document = build_bundle()
        self.registry = Registry().with_resource(API_ID, Resource(self.document, DRAFT202012))
        self.routes = []
        self.seen = set()
        for path, item in self.document["paths"].items():
            parts = re.split(r"\{([^{}]+)}", path)
            pattern = "".join(
                f"(?P<{part}>[^/]+)" if index % 2 else re.escape(part) for index, part in enumerate(parts)
            )
            self.routes.append((path, re.compile(pattern), item))
        self.check_references(self.document)

    def check_references(self, value):
        if isinstance(value, list):
            for element in value:
                self.check_references(element)
        elif isinstance(value, dict):
            if "$ref" in value:
                assert value["$ref"].startswith("#/"), value["$ref"]
                at_pointer(self.document, value["$ref"])
            for element in value.values():
                self.check_references(element)

    def checker(self, location):
        return Draft202012Validator(
            {"$ref": f"{API_ID}#{location}"}, registry=self.registry, format_checker=FORMATS,
        )

    def location(self, location):
        item = at_pointer(self.document, location)
        return item["$ref"][1:] if "$ref" in item else location

    def assert_exchange(self, request, response):
        url = urlsplit(request["path"])
        method = request["method"].lower()
        for path, pattern, item in self.routes:
            match = pattern.fullmatch(url.path)
            if match and method in item:
                break
        else:
            raise AssertionError(f"OpenAPI path missing: {request['method']} {url.path}")
        self.seen.add((path, method))
        path_pointer = pointer("paths", path)
        op_pointer = path_pointer + pointer(method)
        operation = item[method]
        scheme = mock_auth_scheme(request["path"])
        assert operation.get("security", self.document["security"]) == [{scheme: []}]
        definition = self.document["components"]["securitySchemes"][scheme]
        assert (definition["type"], definition["scheme"]) == ("http", "basic")

        inputs = {
            "path": {name: unquote(value, errors="strict") for name, value in match.groupdict().items()},
            "query": parse_qs(url.query, keep_blank_values=True),
            "header": headers_lower(request.get("headers", {})),
        }
        for parent in (path_pointer, op_pointer):
            for index, _ in enumerate(at_pointer(self.document, parent).get("parameters", [])):
                location = self.location(parent + pointer("parameters", str(index)))
                parameter = at_pointer(self.document, location)
                name, scope = parameter["name"], parameter["in"]
                values = inputs[scope]
                value = values.get(name.lower() if scope == "header" else name)
                if value is None:
                    assert not parameter["required"], name
                    continue
                if scope == "query":
                    value, = value
                self.validate_parameter(location + "/schema", value)

        status = str(response["status"])
        if "requestBody" in operation:
            location = op_pointer + pointer("requestBody", "content", MEDIA, "schema")
            if status != "422":
                self.checker(location).validate(request["body"])
        else:
            assert "body" not in request

        location = self.location(op_pointer + pointer("responses", status))
        description = at_pointer(self.document, location)
        received = headers_lower(response.get("headers", {}))
        for name, header in description.get("headers", {}).items():
            value = received.get(name.lower())
            if value is None:
                assert not header.get("required", False), name
                continue
            self.validate_parameter(location + pointer("headers", name, "schema"), value)

        if "content" in description:
            check = self.checker(location + pointer("content", MEDIA, "schema"))
            body = response["body"]
            check.validate(body)
            if response["status"] == 409 and body["error"]["code"] == "DOCUMENT_BUSY" and "conflicts" in body["error"]:
                missing_conflicts = {name: value for name, value in body["error"].items() if name != "conflicts"}
                assert not check.is_valid({"error": missing_conflicts})
        else:
            assert "body" not in response

    def validate_parameter(self, location, value):
        shape = at_pointer(self.document, self.location(location))
        if shape.get("type") == "integer":
            value = int(value)
        self.checker(location).validate(value)

    def assert_coverage(self):
        declared = {
            (path, method)
            for path, _, operations in self.routes
            for method in operations.keys() & METHODS
        }
        assert self.seen == declared, declared - self.seen
        operation_ids = {self.document["paths"][path][method]["operationId"] for path, method in declared}
        assert len(operation_ids) == len(declared)
        return len(operation_ids)


def headers_lower(headers):
    return {name.lower(): value for name, value in headers.items()}


def send(client, method, path, body=None, headers=None, *, authenticated=True, credential_scheme=None):
    outgoing = dict(headers or {})
    if authenticated:
        credentials = MOCK_CREDENTIALS[credential_scheme or mock_auth_scheme(path)]
        outgoing["Authorization"] = "Basic " + b64encode(credentials.encode()).decode()
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode()
        outgoing["Content-Type"] = MEDIA
    client.request(method, path, body=payload, headers=outgoing)
    raw = client.getresponse()
    result = {"status": raw.status, "headers": dict(raw.getheaders())}
    data = raw.read()
    if data:
        assert raw.getheader("Content-Type") == MEDIA
        result["body"] = json.loads(data)
    elif raw.status == 204:
        assert raw.getheader("Content-Type") is None
        assert raw.getheader("Content-Length") is None
    return result


def reset(client, scenario):
    assert send(client, "POST", "/__mock/reset", {"scenario": scenario})["status"] == 204


def assert_controls(client, scenarios, api):
    challenge = send(client, "GET", "/health/live", authenticated=False)
    assert challenge["status"] == 401
    assert challenge["body"]["error"]["code"] == "UNAUTHENTICATED"
    api.assert_exchange({"method": "GET", "path": "/health/live"}, challenge)

    reset(client, "happy_path")
    invalid = send(client, "POST", "/__mock/reset", {"scenario": "does-not-exist"})
    assert invalid["status"] == 400
    assert invalid["body"]["error"]["code"] == "MOCK_SCENARIO_INVALID"
    mismatch = send(client, "GET", "/not-in-this-scenario")
    assert mismatch["status"] == 409
    assert mismatch["body"]["error"]["code"] == "MOCK_STEP_MISMATCH"
    first = scenarios["happy_path"][0]["request"]
    assert send(client, first["method"], first["path"])["status"] == 200

    # Check that a credential for another route cannot access or advance the scenario.
    for suffix, wrong_schemes in (
        ("/internal/v1/catalog", ("systemIngestionBasic", "systemInferenceBasic")),
        ("/v1/ingestions", ("runtimeManagementBasic", "systemInferenceBasic")),
        ("/v1/queries", ("runtimeManagementBasic", "systemIngestionBasic")),
    ):
        target = next(step["request"] for step in scenarios["happy_path"] if step["request"]["path"].endswith(suffix))
        for wrong_scheme in wrong_schemes:
            response = send(client, target["method"], target["path"], fixture_body(target),
                            credential_scheme=wrong_scheme)
            assert response["status"] == 401, (target["path"], wrong_scheme)
            assert response["body"]["error"]["code"] == "UNAUTHENTICATED"
            api.assert_exchange(target, response)


def run(scenarios, client, api):
    observed = {}
    for name, steps in scenarios.items():
        reset(client, name)
        observed[name] = []
        last_poll = None
        for index, step in enumerate(steps, 1):
            request, expected = step["request"], step["response"]
            try:
                actual = send(client, request["method"], request["path"], fixture_body(request), request.get("headers"))
                assert actual["status"] == expected["status"], (expected["status"], actual["status"], actual.get("body"))
                expected_headers = expected.get("headers", {})
                actual_headers = headers_lower(actual["headers"])
                for header, value in expected_headers.items():
                    assert actual_headers.get(header.lower()) == value, header
                if "body" in expected or "body_file" in expected:
                    assert actual.get("body") == fixture_body(expected)
                else:
                    assert "body" not in actual
                api.assert_exchange(request, actual)

                actual["headers"] = {
                    name: value for name, value in actual["headers"].items() if name.lower() not in TRANSPORT_HEADERS
                }
                observed[name].append({"request": request, "response": actual})
                if request["method"] == "GET" and "/v1/ingestions/" in request["path"]:
                    last_poll = request["path"], actual["body"]
            except (AssertionError, KeyError) as error:
                raise AssertionError(f"{name} step {index}: {request['method']} {request['path']}: {error}") from error

        if last_poll:
            path, expected_body = last_poll
            assert send(client, "GET", path)["body"] == expected_body, name

    verify(observed)


def main():
    scenarios = load_scenarios()
    api = OpenAPIContract()
    with create_server(scenarios, "happy_path", 0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=5)) as client:
                assert_controls(client, scenarios, api)
                run(scenarios, client, api)
                print(f"PASS: {api.assert_coverage()} OpenAPI operations exercised over HTTP")
        finally:
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    main()
