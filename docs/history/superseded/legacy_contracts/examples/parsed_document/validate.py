"""Local ParsedDocument 0.2 shape checks, not a Parser implementation."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parents[2]
def validate_document(document):
    schema = json.loads((ROOT / 'schemas/parsed_document.schema.json').read_text())
    Draft202012Validator(schema).validate(document)
    json.dumps(document, allow_nan=False)
    for key in ('document_id', 'source_revision'):
        if not document[key].strip():
            raise ValueError('blank identity')
    for unit in document['units']:
        if any(not key.strip() for key in unit):
            raise ValueError('blank unit field name')
    # Required nonblank split/copy fields are validated against the selected task.
