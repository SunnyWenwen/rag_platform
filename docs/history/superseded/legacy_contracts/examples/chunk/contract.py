"""Chunk draft helpers. Local schemas only; not a Chunker or production SDK.

Requires jsonschema>=4.18,<5. Slices in the fixtures are explicit conformance
inputs, not implementations of Fixed-size / Recursive / Header-aware.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
CHUNK_ID = 'urn:rag-builder:chunk:0.2-draft'


def local_registry() -> Registry:
    """No registry lookup performs network access."""
    registry = Registry()
    for name in ('parsed_document', 'chunk', 'inference_context'):
        schema = json.loads((ROOT / 'schemas' / f'{name}.schema.json').read_text())
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema['$id'], Resource.from_contents(schema))
    return registry


def canonical_json(value: object) -> bytes:
    """Reference encoding: UTF-8, sorted keys, compact JSON, finite numbers.

    No Unicode normalization; input strings are preserved. This Python reference
    is not a promise of cross-language RFC 8785 canonicalization.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def validate_spec(spec: dict) -> None:
    """Validate the fixture's resolved plan, not the complete Pipeline Config."""
    canonical_json(spec)
    if set(spec) != {'spec_version', 'tasks'} or spec['spec_version'] != 'chunking-spec/0.1-draft':
        raise ValueError('unknown chunking spec version or keys')
    if not isinstance(spec['tasks'], list) or not spec['tasks']:
        raise ValueError('at least one task is required')
    ids = []
    for task in spec['tasks']:
        if set(task) != {'task_id', 'component_id', 'component_version', 'split_field',
                         'output_field', 'copy_fields', 'parameters'}:
            raise ValueError('task must contain resolved component and field mappings')
        for key in ('task_id', 'component_id', 'component_version', 'split_field', 'output_field'):
            if not isinstance(task[key], str) or not task[key].strip():
                raise ValueError('task identity and field names must be nonempty strings')
        ids.append(task['task_id'])
        if not isinstance(task['parameters'], dict) or not isinstance(task['copy_fields'], list):
            raise ValueError('parameters must be an object; copy_fields must be an array')
        outputs = [task['output_field']]
        for mapping in task['copy_fields']:
            if set(mapping) != {'source_field', 'output_field'} or any(
                not isinstance(v, str) or not v.strip() for v in mapping.values()
            ):
                raise ValueError('copy mapping requires two nonempty field names')
            outputs.append(mapping['output_field'])
        if len(outputs) != len(set(outputs)):
            raise ValueError('split/copy output names collide')
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate task_id')


def fingerprint(spec: dict) -> str:
    validate_spec(spec)
    return hashlib.sha256(canonical_json(spec)).hexdigest()


def chunk_id(document_id: str, source_revision: str, digest: str, ordinal: int) -> str:
    payload = {'document_id': document_id, 'source_revision': source_revision,
               'chunking_fingerprint': digest, 'chunk_ordinal': ordinal}
    return 'chk_' + hashlib.sha256(canonical_json(payload)).hexdigest()


def assemble_fixture_chunk(source: dict, spec: dict, task_id: str, ordinal: int,
                           text: str, refs: list[dict], unit_index: int = 0) -> dict:
    """Assemble already-cut fixture text. Does not calculate slicing boundaries."""
    digest = fingerprint(spec)
    task = next(t for t in spec['tasks'] if t['task_id'] == task_id)
    fields = {task['output_field']: text}
    source_refs = deepcopy(refs)
    for ref in source_refs:
        ref.setdefault('unit_index', unit_index)
    for mapping in task['copy_fields']:
        src, dest = mapping['source_field'], mapping['output_field']
        if src not in source['units'][unit_index]:
            raise ValueError(f'missing explicitly copied field: {src}')
        fields[dest] = deepcopy(source['units'][unit_index][src])
        source_refs.append({'unit_index': unit_index, 'field': src, 'output_field': dest, 'role': 'copy'})
    metadata = deepcopy(source['metadata'])
    rag = metadata.setdefault('_rag', {})
    # source is already trusted/validated ParsedDocument; callers cannot supply
    # trusted _rag keys through an unchecked API body.
    rag['source_refs'] = source_refs
    rag['chunking'] = {'chunking_fingerprint': digest,
                       'chunk_ordinal': ordinal, 'task_id': task_id}
    return {'chunk_id': chunk_id(source['document_id'], source['source_revision'], digest, ordinal),
            'document_id': source['document_id'], 'source_revision': source['source_revision'],
            'fields': fields, 'metadata': metadata, 'vectors': {}}


def _range(ref: dict, prefix: str, text: str) -> str:
    start, end = ref[prefix + 'start'], ref[prefix + 'end']
    if not isinstance(text, str) or not 0 <= start < end <= len(text):
        raise ValueError('invalid or empty code-point range')
    return text[start:end]


def _validate_ref(chunk: dict, ref: dict, source: dict | None) -> None:
    if ref['output_field'] not in chunk['fields']:
        raise ValueError('source ref points to absent output field')
    output = chunk['fields'][ref['output_field']]
    if 'chunk_start' in ref:
        output = _range(ref, 'chunk_', output)
    if ref['role'] == 'copy' and any(k in ref for k in ('start', 'chunk_start')):
        raise ValueError('copy represents a complete unit field')
    if 'start' in ref and ref['start'] >= ref['end']:
        raise ValueError('empty or inverted source range')
    if source is None:
        return
    unit_index = ref['unit_index']
    if unit_index >= len(source['units']):
        raise ValueError('unit_index out of range')
    unit = source['units'][unit_index]
    if ref['field'] not in unit:
        raise ValueError('source unit field missing')
    original = unit[ref['field']]
    if 'start' in ref:
        original = _range(ref, '', original)
    if output != original:
        raise ValueError('source selector does not reproduce output')


def validate_chunk(chunk: dict, *, source: dict | None = None,
                   effective_spec: dict | None = None, vector_bindings: dict | None = None,
                   require_provenance: bool = False, require_empty_vectors: bool = False) -> None:
    """Shape + available context. Generic transferred chunks may omit _rag.

    Chunker output uses require_empty_vectors=True. Provenance is optional;
    require_provenance=True explicitly opts into the full reference annotation
    checks for fixtures/components that promise them. Embedding/Indexing supplies
    vector_bindings. No generic Engine gate requires these annotations.
    effective_spec selects the reference helper checks for annotations that exist;
    it never makes absent annotations mandatory. Source locations are producer
    annotations, not character-level bbox proof.
    """
    schema = json.loads((ROOT / 'schemas/chunk.schema.json').read_text())
    Draft202012Validator(schema, registry=local_registry()).validate(chunk)
    canonical_json(chunk)  # Reject NaN/Infinity and non-JSON payloads.
    if not chunk['chunk_id'].strip() or not chunk['document_id'].strip() or not chunk['source_revision'].strip():
        raise ValueError('whitespace-only identity')
    rag = chunk['metadata'].get('_rag', {})
    if require_provenance and ('source_refs' not in rag or 'chunking' not in rag):
        raise ValueError('full Chunker output requires source_refs and chunking identity')
    if require_empty_vectors and chunk['vectors']:
        raise ValueError('Chunker must not generate vectors')
    if source is not None and effective_spec is not None:
        for unit in source['units']:
            for task in effective_spec['tasks']:
                value = unit.get(task['split_field'])
                if not isinstance(value, str) or not value.strip():
                    raise ValueError('missing/blank/nonstring split field')
                if any(m['source_field'] not in unit for m in task['copy_fields']):
                    raise ValueError('missing copy field')
    if source is not None:
        if (chunk['document_id'], chunk['source_revision']) != (source['document_id'], source['source_revision']):
            raise ValueError('document identity was not inherited')
        business = {k: v for k, v in source['metadata'].items() if k != '_rag'}
        if {k: v for k, v in chunk['metadata'].items() if k != '_rag'} != business:
            raise ValueError('business metadata must be inherited without projection or mutation')
        for key, value in source['metadata'].get('_rag', {}).items():
            if key not in ('source_refs', 'chunking') and rag.get(key) != value:
                raise ValueError('trusted platform metadata was dropped or changed')
    if len({r['unit_index'] for r in rag.get('source_refs', [])}) > 1:
        raise ValueError('a chunk cannot merge different units')
    for ref in rag.get('source_refs', []):
        _validate_ref(chunk, ref, source)
    if effective_spec is not None and 'chunking' in rag:
        digest = fingerprint(effective_spec)
        info = rag.get('chunking', {})
        if info.get('chunking_fingerprint') != digest:
            raise ValueError('effective spec fingerprint mismatch')
        task = next((t for t in effective_spec['tasks'] if t['task_id'] == info.get('task_id')), None)
        if task is None:
            raise ValueError('unknown task_id')
        if chunk['chunk_id'] != chunk_id(chunk['document_id'], chunk['source_revision'], digest, info['chunk_ordinal']):
            raise ValueError('chunk_id mismatch')
        expected_fields = {task['output_field']} | {m['output_field'] for m in task['copy_fields']}
        if set(chunk['fields']) != expected_fields:
            raise ValueError('fields differ from split/copy mappings')
        split_refs = [r for r in rag.get('source_refs', []) if r['role'] == 'split']
        if (require_provenance and not split_refs) or any(r['field'] != task['split_field'] or r['output_field'] != task['output_field'] for r in split_refs):
            raise ValueError('split provenance differs from task')
        # This reference path supports exact slices within a single Unit.
        # A custom content transform needs its own declared semantic validator.
        output = chunk['fields'][task['output_field']]
        if not isinstance(output, str) or not output.strip():
            raise ValueError('reference text task requires nonblank string output')
        if any('chunk_start' in r for r in split_refs):
            cursor = 0
            for ref in split_refs:
                if 'chunk_start' not in ref or ref['chunk_start'] < cursor:
                    raise ValueError('output selectors must be complete and ordered without overlap')
                gap = output[cursor:ref['chunk_start']]
                if (cursor == 0 and gap) or gap not in ('', '\n\n'):
                    raise ValueError('unexplained text outside source selectors')
                cursor = ref['chunk_end']
            if cursor != len(output):
                raise ValueError('unexplained trailing text outside source selectors')
        elif split_refs and len(split_refs) != 1:
            raise ValueError('multiple exact slices require explicit output selectors')
        expected_copies = {(m['source_field'], m['output_field']) for m in task['copy_fields']}
        actual_copies = [(r['field'], r['output_field']) for r in rag.get('source_refs', []) if r['role'] == 'copy']
        if (require_provenance or actual_copies) and (len(actual_copies) != len(expected_copies) or set(actual_copies) != expected_copies):
            raise ValueError('copy provenance differs from task')
    for name, vector in chunk['vectors'].items():
        if vector['source_field'] not in chunk['fields']:
            raise ValueError('vector source field is absent')
        if vector_bindings is not None:
            if name not in vector_bindings:
                raise ValueError('unbound vector name')
            binding = vector_bindings[name]
            if (vector['embedding_profile_id'], vector['source_field'], len(vector['values'])) != (
                binding['embedding_profile_id'], binding['source_field'], binding['dimensions']
            ):
                raise ValueError('vector profile/source/dimension differs from binding')


def validate_sequence(chunks: list[dict], spec: dict, source: dict | None = None,
                      *, require_provenance: bool = False) -> None:
    """Validate a document's output; reference trace/order checks are conditional.

    Missing annotations are legal even with source/spec. A caller may opt into
    strict reference provenance tests; this is not required by the public DTO.
    """
    validate_spec(spec)
    if not chunks:
        raise ValueError('fixture document produced no chunks; empty-document policy is separate')
    if len({(c['document_id'], c['source_revision']) for c in chunks}) != 1:
        raise ValueError('sequence must belong to one document revision')
    for chunk in chunks:
        validate_chunk(chunk, source=source, effective_spec=spec,
                       require_provenance=require_provenance, require_empty_vectors=True)
    if len({c['chunk_id'] for c in chunks}) != len(chunks):
        raise ValueError('duplicate chunk_id')
    # Only complete reference annotations justify checking the reference order.
    # Without them, do not infer missing task IDs or source positions.
    if not all(c['metadata'].get('_rag', {}).get('source_refs') and
               c['metadata'].get('_rag', {}).get('chunking') for c in chunks):
        return
    order = {task['task_id']: i for i, task in enumerate(spec['tasks'])}
    task_order = []
    for ordinal, chunk in enumerate(chunks):
        info = chunk['metadata']['_rag']['chunking']
        if info['chunk_ordinal'] != ordinal:
            raise ValueError('ordinals must be globally contiguous, starting from zero')
        unit_index = chunk['metadata']['_rag']['source_refs'][0]['unit_index']
        task_order.append((order[info['task_id']], unit_index))
    if task_order != sorted(task_order):
        raise ValueError('task output order differs from resolved spec')
    if {x[0] for x in task_order} != set(order.values()):
        raise ValueError('each required task must produce at least one chunk')
    if source is not None and set(task_order) != {(t, u) for t in order.values() for u in range(len(source['units']))}:
        raise ValueError('every required task/unit must produce chunks')
