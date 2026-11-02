"""Run with Python; no provider model/network execution."""
from copy import deepcopy
import json
from pathlib import Path
from validate import validate_document
from jsonschema import ValidationError
HERE = Path(__file__).parent
positive = ['plain_text', 'units', 'table_rows', 'image_description', 'docling_report_excerpt']
for name in positive:
    validate_document(json.loads((HERE / (name + '.json')).read_text()))
base = json.loads((HERE / 'units.json').read_text())
bad = []
for key in ('document_id','source_revision','units','metadata'):
    x=deepcopy(base); del x[key]; bad.append(x)
for units in ({'text':'old'}, [], ['text'], [{}], [{'text':42}]):
    x=deepcopy(base); x['units']=units; bad.append(x)
for key,value in [('fields', {'text':'old'}), ('structure', {})]:
    x=deepcopy(base); x[key]=value; bad.append(x)
x=deepcopy(base); x['document_id']=' '; bad.append(x)
for x in bad:
    try: validate_document(x)
    except (ValueError, ValidationError): pass
    else: raise AssertionError('invalid fixture accepted')
# Custom string field is permitted; no mandatory unit_id or fields wrapper.
x=deepcopy(base); x['units']=[{'body':'custom text', 'unit_id':'optional'}]; validate_document(x)
print(f'ParsedDocument: {len(positive)+1} positives, {len(bad)} negatives passed')
