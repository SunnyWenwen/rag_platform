"""ParsedDocument draft conformance helper; not the production Engine SDK.

Requires jsonschema>=4.18,<5. Extra schemas are supplied explicitly by a trusted
caller; identifiers never trigger network downloads or Python imports.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / 'schemas/parsed_document.schema.json'
TEXT_SPANS = 'text-spans/0.1-draft'
PAGE_BLOCKS = 'page-blocks/0.1-draft'


def rendered_page_text(structure: dict) -> str:
    """Page/block authoritative text: reading order, nonempty text, two LF joiner.

    Empty/visual-only blocks add no fake text. Blank pages remain in pages, but
    do not add text. Do not infer page breaks or source offsets from the joiner.
    """
    return '\n\n'.join(
        block['text'] for page in structure['pages'] for block in page['blocks']
        if block.get('text')
    )


def _check_registered_schema(schema: Any) -> None:
    """Keep explicit registry schemas local; identifiers do not enable fetching."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in ('$ref', '$dynamicRef') and isinstance(value, str) and not value.startswith('#'):
                raise ValueError('registered schemas may only use local fragment references')
            _check_registered_schema(value)
    elif isinstance(schema, list):
        for value in schema:
            _check_registered_schema(value)


def validate_document(document: dict, *, structure_schemas: dict | None = None,
                      block_schemas: dict | None = None) -> None:
    """Validate JSON shape plus invariants that JSON Schema cannot express."""
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator(schema).validate(document)
    structure_schemas = structure_schemas or {}
    block_schemas = block_schemas or {}
    # JSON numbers must be finite, including nested business data/extensions.
    json.dumps(document, allow_nan=False)

    for field, structure in document['structure'].items():
        if field not in document['fields']:
            raise ValueError(f'structure.{field}: no corresponding fields key')
        schema_id = structure['schema_id']
        if schema_id not in (TEXT_SPANS, PAGE_BLOCKS):
            if schema_id not in structure_schemas:
                raise ValueError(f'unregistered structure schema: {schema_id}')
            _check_registered_schema(structure_schemas[schema_id])
            Draft202012Validator.check_schema(structure_schemas[schema_id])
            Draft202012Validator(structure_schemas[schema_id]).validate(structure['payload'])
            continue
        text = document['fields'][field]
        if not isinstance(text, str):
            raise ValueError(f'{field}: builtin text structures require string')
        if schema_id == TEXT_SPANS:
            blocks = structure['blocks']
            page_numbers = []
            for page in structure.get('pages', []):
                if not 0 <= page['start'] <= page['end'] <= len(text):
                    raise ValueError('invalid page span')
                page_numbers.append(page['page_number'])
            previous_start = -1
            for block in blocks:
                if 'start' in block:
                    if not 0 <= block['start'] <= block['end'] <= len(text):
                        raise ValueError('invalid text span')
                    if block['type'] in ('heading', 'paragraph', 'list_item', 'code') and block['start'] == block['end']:
                        raise ValueError('empty textual block')
                    if block['start'] < previous_start:
                        raise ValueError('block reading order conflicts with text offsets')
                    previous_start = block['start']
            points = [p['offset'] for p in structure.get('split_points', [])]
            if points != sorted(set(points)) or any(p <= 0 or p >= len(text) for p in points):
                raise ValueError('split offsets must be unique, ordered, interior positions')
        else:
            page_numbers = [p['page_number'] for p in structure['pages']]
            blocks = [b for p in structure['pages'] for b in p['blocks']]
            if text != rendered_page_text(structure):
                raise ValueError('derived fields text differs from authoritative page/block text')
        if page_numbers != sorted(set(page_numbers)):
            raise ValueError('page numbers must be unique and increasing; gaps are allowed')

        ids = [b['block_id'] for b in blocks]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate block_id within a field')
        by_id = {b['block_id']: b for b in blocks}
        for index, block in enumerate(blocks):
            for relation in ('parent_id', 'continuation_of'):
                if relation in block and block[relation] not in by_id:
                    raise ValueError(f'dangling {relation}')
                seen = {block['block_id']}
                current = block
                while relation in current:
                    target = current[relation]
                    if target not in by_id:
                        raise ValueError(f'dangling {relation}')
                    if target in seen:
                        raise ValueError(f'cyclic {relation}')
                    seen.add(target)
                    current = by_id[target]
            if 'continuation_of' in block and block['continuation_of'] not in ids[:index]:
                raise ValueError('continuation must refer to an earlier block')
            if 'data_ref' in block and block['data_ref'] not in document['fields']:
                raise ValueError('data_ref must name an existing fields entry')
            if block['type'] == 'extension':
                extension_type = block['extension_type']
                if extension_type not in block_schemas:
                    raise ValueError(f'unregistered extension block: {extension_type}')
                _check_registered_schema(block_schemas[extension_type])
                Draft202012Validator.check_schema(block_schemas[extension_type])
                Draft202012Validator(block_schemas[extension_type]).validate(document['fields'][block['data_ref']])
            for location in block.get('locations', []):
                bbox = location.get('bbox')
                if not bbox:
                    continue
                if bbox['left'] > bbox['right']:
                    raise ValueError('inverted horizontal bbox')
                if bbox['origin'] == 'top-left' and bbox['top'] > bbox['bottom']:
                    raise ValueError('inverted top-left bbox')
                if bbox['origin'] == 'bottom-left' and bbox['top'] < bbox['bottom']:
                    raise ValueError('inverted bottom-left bbox')
                if bbox['unit'] == 'normalized' and any(not 0 <= bbox[k] <= 1 for k in ('left', 'top', 'right', 'bottom')):
                    raise ValueError('normalized bbox outside [0,1]')
        if schema_id == PAGE_BLOCKS:
            targets = [p['before_block_id'] for p in structure.get('split_points', [])]
            if any(t not in by_id for t in targets) or len(targets) != len(set(targets)):
                raise ValueError('invalid page/block split target')
            if targets and (targets != sorted(targets, key=ids.index) or targets[0] == ids[0]):
                raise ValueError('split targets must be ordered interior block boundaries')


if __name__ == '__main__':
    import sys
    for filename in sys.argv[1:]:
        validate_document(json.loads(Path(filename).read_text()))
        print(f'PASS {filename}')
