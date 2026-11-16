"""Verify batch input, vector output, and externally retrieved candidates."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE.parents[1] / "schemas"


def read(path):
    return json.loads(path.read_text())


SCHEMA_NAMES = ("document", "ingestion_request", "inference_request", "query_context")
schemas = {name: read(SCHEMAS / f"{name}.schema.json") for name in SCHEMA_NAMES}
registry = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
)
for schema in schemas.values():
    Draft202012Validator.check_schema(schema)


def validator(schema):
    return Draft202012Validator(schema, registry=registry)


def reject(check, value):
    try:
        check.validate(value)
    except ValidationError:
        return
    raise AssertionError("Expected invalid contract payload")


batch = read(HERE / "ingestion.request.json")
batch_check = validator(schemas["ingestion_request"])
batch_check.validate(batch)
reject(batch_check, {"documents": []})
reject(batch_check, batch["documents"])
reject(batch_check, {"documents": [{**batch["documents"][0], "parameters": {}}]})
remote_ingestion = read(HERE / "remote_ingestion.request.json")
assert remote_ingestion["input"] == batch["documents"][0]
assert remote_ingestion["parameters"] == {"language": batch["parameters"]["language"]}

vector_check = validator(read(HERE / "remote_ingestion.response.schema.json"))
output = read(HERE / "remote_ingestion.response.json")
vector_check.validate(output)
wrong_dimension = deepcopy(output)
wrong_dimension["output"][0]["vectors"]["text"]["values"].pop()
reject(vector_check, wrong_dimension)
wrong_profile = deepcopy(output)
wrong_profile["output"][0]["vectors"]["text"]["embedding_profile_id"] = "other"
reject(vector_check, wrong_profile)

inference = read(HERE / "inference.request.json")
inference_check = validator(schemas["inference_request"])
inference_check.validate(inference)
invalid_filters = ([{"any": []}], [{"any": inference["filters"]}],
                   [{"field": "structdata.tags", "operator": "in", "value": []}],
                   [{"field": "structdata.price", "operator": "eq", "value": None}],
                   [{"field": "metadata.department", "operator": "eq", "value": "製造部"}])
query_check = validator(schemas["query_context"])
remote_input = read(HERE / "remote_retrieval.request.json")["input"]
query_check.validate(remote_input)
for filters in invalid_filters:
    reject(inference_check, {**inference, "filters": filters})
    reject(query_check, [{**remote_input[0], "filters": filters}])
system_config = read(HERE.parent / "system_config" / "local_memory.builtin.json")
fixed_filters = system_config["config"]["pipelines"]["inference"]["fixed_filters"]
assert remote_input[0]["filters"] == fixed_filters + inference["filters"]
contexts = read(HERE / "remote_retrieval.response.json")["output"]
query_check.validate(contexts)
candidate = contexts[0]["result_sets"][0]["items"][0]["data"]
effective_check = validator(read(HERE / "effective_document.schema.json"))
effective_check.validate(candidate)
wrong_field = deepcopy(candidate)
wrong_field["structdata"]["text"] = 123
reject(effective_check, wrong_field)
wrong_field["structdata"]["text"] = ["設備", "保養"]
reject(effective_check, wrong_field)
empty_tags = deepcopy(candidate)
empty_tags["structdata"]["tags"] = []
effective_check.validate(empty_tags)
print("PASS: batch, embedding output, fixed and dynamic Filter shape, and effective external Retrieval schema")
