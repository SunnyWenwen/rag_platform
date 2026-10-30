"""Small executable contract cases, not Engine/Chunker integration tests."""
from copy import deepcopy
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from validate import validate_document, SCHEMA_PATH


def run():
    here = Path(__file__).parent
    Draft202012Validator.check_schema(json.loads(SCHEMA_PATH.read_text()))
    plain, spans, pages = [json.loads((here / name).read_text()) for name in ('plain_text.json', 'text_spans.json', 'page_blocks.json')]
    positive = [plain, spans, pages]
    unicode_case = deepcopy(spans)
    unicode_case['fields']['text'] = 'A😀B'
    unicode_case['structure']['text'] = {'schema_id': 'text-spans/0.1-draft', 'blocks': [
        {'block_id': 'emoji', 'type': 'paragraph', 'start': 1, 'end': 2}
    ]}
    positive.append(unicode_case)
    gap = deepcopy(pages)
    gap['structure']['text']['pages'][1]['page_number'] = 9
    positive.append(gap)
    image_only = deepcopy(plain)
    image_only['fields'] = {'text': '', 'image': {'uri': 'https://example.com/image.png'}}
    image_only['structure'] = {'text': {'schema_id': 'text-spans/0.1-draft', 'blocks': [
        {'block_id': 'image', 'type': 'image', 'data_ref': 'image'}
    ]}}
    positive.append(image_only)
    for case in positive:
        validate_document(case)
    negative = []

    def invalid(base, edit):
        value = deepcopy(base)
        edit(value)
        negative.append(value)

    invalid(plain, lambda d: d.pop('structure'))
    invalid(plain, lambda d: d.update(vectors={}))
    invalid(plain, lambda d: d.update(source_revision=None))
    invalid(plain, lambda d: d.update(fields={}))
    invalid(plain, lambda d: d['fields'].update(x=float('nan')))
    invalid(spans, lambda d: d['structure'].update(missing=d['structure']['text']))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(end=999))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(start=4, end=0))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(start=0, end=0))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(end=None))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(level=0))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(surprise=1))
    invalid(spans, lambda d: d['structure']['text']['blocks'][1].update(block_id='b1'))
    invalid(spans, lambda d: d['structure']['text']['blocks'][1].update(parent_id='missing'))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(parent_id='b2'))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(continuation_of='b2'))
    invalid(spans, lambda d: d['structure']['text']['split_points'][0].update(offset=999))
    invalid(spans, lambda d: d['structure']['text']['split_points'].append(d['structure']['text']['split_points'][0]))
    invalid(spans, lambda d: d['structure']['text']['blocks'][1].update(data_ref='missing'))
    invalid(pages, lambda d: d['fields'].update(text='a different rendering'))
    invalid(pages, lambda d: d['structure']['text']['pages'][1].update(page_number=1))
    invalid(pages, lambda d: d['structure']['text']['split_points'][0].update(before_block_id='missing'))
    invalid(unicode_case, lambda d: d['structure']['text']['blocks'][0].update(end=4))
    invalid(image_only, lambda d: d['structure']['text']['blocks'][0].pop('data_ref'))
    invalid(image_only, lambda d: d['structure']['text']['blocks'][0].update(type='extension'))
    invalid(image_only, lambda d: d['structure']['text']['blocks'][0].update(type='extension', extension_type='company.unknown/1'))
    invalid(spans, lambda d: d['structure']['text']['blocks'][0].update(locations=[{
        'kind': 'page', 'page_number': 1,
        'bbox': {'left': 0.8, 'top': 0.1, 'right': 0.2, 'bottom': 0.9, 'origin': 'top-left', 'unit': 'normalized'}
    }]))
    for case in negative:
        try:
            validate_document(case)
        except (ValueError, ValidationError):
            pass
        else:
            raise AssertionError('invalid case accepted')

    custom = deepcopy(plain)
    custom['fields']['text'] = 'custom content'
    custom['structure'] = {'text': {'schema_id': 'company.custom/1', 'payload': {'section': 'intro'}}}
    registry = {'company.custom/1': {'type': 'object', 'required': ['section'], 'properties': {'section': {'type': 'string'}}, 'additionalProperties': False}}
    validate_document(custom, structure_schemas=registry)
    for candidate in ({}, {'company.custom/1': {'$ref': 'https://example.com/remote-schema'}}):
        try:
            validate_document(custom, structure_schemas=candidate)
        except (ValueError, ValidationError):
            pass
        else:
            raise AssertionError('unregistered or externally resolving schema accepted')
    report = {'json_schema_meta_validation': True, 'positive_cases': len(positive) + 1,
              'negative_cases': len(negative) + 2,
              'scope': 'Schema and cross-field reference semantics; no parser or Chunker execution'}
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == '__main__':
    run()
