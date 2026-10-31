"""Build deterministic contract fixtures from explicitly supplied text slices.

No tokenizer, Chunker, model API or database is invoked.
"""
from copy import deepcopy
import json
from pathlib import Path

from contract import assemble_fixture_chunk, validate_chunk, validate_sequence

HERE = Path(__file__).parent


def task(task_id='text', split='text', output='text', copies=()):
    return {'task_id': task_id, 'component_id': 'example.recursive-token',
            'component_version': '1.0.0-fixture', 'split_field': split, 'output_field': output,
            'copy_fields': [{'source_field': src, 'output_field': dest} for src, dest in copies],
            'parameters': {'chunk_size': 512, 'overlap': 64,
                           'tokenizer_id': 'fixture-tokenizer', 'tokenizer_revision': 'v1',
                           'separators': ['\n\n', '\n', '。'], 'keep_separator': True}}


def spec(*tasks):
    return {'spec_version': 'chunking-spec/0.1-draft', 'tasks': list(tasks)}


def document(document_id='manual-001', fields=None, metadata=None, structure=None):
    return {'document_id': document_id, 'source_revision': 'v1',
            'fields': fields if fields is not None else {'text': '保養規範\n清潔前先斷電。'},
            'metadata': metadata if metadata is not None else {'department': 'engineering'},
            'structure': structure if structure is not None else {}}


def sliced(source, plan, task_id, ordinal, start, end, **selectors):
    t = next(t for t in plan['tasks'] if t['task_id'] == task_id)
    text = source['fields'][t['split_field']][start:end]
    ref = {'field': t['split_field'], 'output_field': t['output_field'],
           'role': 'split', 'start': start, 'end': end, **selectors}
    return assemble_fixture_chunk(source, plan, task_id, ordinal, text, [ref])


def build_cases():
    cases = []
    source, plan = document(), spec(task())
    chunks = [sliced(source, plan, 'text', 0, 5, 12)]
    cases.append({'case_id': 'default_text', 'source': source, 'effective_spec': plan,
                  'chunks': chunks})

    source = document(fields={'text': '保養規範\n清潔前先斷電。', 'title': '設備手冊'})
    plan = spec(task(copies=[('text', 'original_text'), ('title', 'title')]))
    cases.append({'case_id': 'copy_original', 'source': source, 'effective_spec': plan,
                  'chunks': [sliced(source, plan, 'text', 0, 5, 12)]})

    source = document('multi-001', {'text': '甲段。乙段。', 'faq': '問一。問二。問三。'})
    plan = spec(task('text', 'text', 'text', [('faq', 'original_faq')]),
                task('faq', 'faq', 'text', [('text', 'original_text')]))
    chunks = [sliced(source, plan, 'text', i, i * 3, i * 3 + 3) for i in range(2)]
    chunks += [sliced(source, plan, 'faq', i + 2, i * 3, i * 3 + 3) for i in range(3)]
    cases.append({'case_id': 'two_plus_three', 'source': source, 'effective_spec': plan,
                  'chunks': chunks})

    source = json.loads((HERE.parent / 'parsed_document/text_spans.json').read_text())
    plan = spec(task())
    cases.append({'case_id': 'text_spans', 'source': source, 'effective_spec': plan,
                  'chunks': [sliced(source, plan, 'text', 0, 5, 12,
                                     schema_id='text-spans/0.1-draft', block_id='b2',
                                     locations=[{'kind': 'page', 'page_number': 1}])]})

    source = json.loads((HERE.parent / 'parsed_document/page_blocks.json').read_text())
    plan = spec(task())
    pages = source['structure']['text']['pages']
    refs, texts, cursor = [], [], 0
    for page in pages:
        for block in page['blocks']:
            text = block['text']
            if texts:
                cursor += 2
            refs.append({'field': 'text', 'output_field': 'text', 'role': 'split',
                         'schema_id': 'page-blocks/0.1-draft', 'block_id': block['block_id'],
                         'block_start': 0, 'block_end': len(text),
                         'chunk_start': cursor, 'chunk_end': cursor + len(text),
                         'locations': [{'kind': 'page', 'page_number': page['page_number']}]})
            texts.append(text)
            cursor += len(text)
    cases.append({'case_id': 'page_blocks', 'source': source, 'effective_spec': plan,
                  'chunks': [assemble_fixture_chunk(source, plan, 'text', 0, '\n\n'.join(texts), refs)]})

    source = document('table-001', {'text': '設備 A 每月保養。'}, {
        'department': 'engineering',
        'maintenance_table': {'columns': ['設備', '週期'], 'rows': [['A', '每月']]}})
    plan = spec(task())
    cases.append({'case_id': 'auxiliary_metadata', 'source': source, 'effective_spec': plan,
                  'chunks': [sliced(source, plan, 'text', 0, 0, len(source['fields']['text']))]})

    embedded = deepcopy(cases[0])
    embedded['case_id'] = 'embedded'
    embedded['chunks'][0]['vectors'] = {'text': {'values': [0.12, -0.08, 0.31],
                                                'embedding_profile_id': 'embedding-demo-v1',
                                                'source_field': 'text'}}
    embedded['vector_bindings'] = {'text': {'embedding_profile_id': 'embedding-demo-v1',
                                           'source_field': 'text', 'dimensions': 3}}
    cases.append(embedded)
    return cases


def main():
    cases = build_cases()
    for case in cases:
        for chunk in case['chunks']:
            validate_chunk(chunk, source=case['source'], effective_spec=case['effective_spec'],
                           vector_bindings=case.get('vector_bindings'), require_provenance=True,
                           require_empty_vectors=case['case_id'] != 'embedded')
        if case['case_id'] != 'embedded':
            validate_sequence(case['chunks'], case['effective_spec'])
    (HERE / 'cases.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'chunks': sum(len(c['chunks']) for c in cases)}))


if __name__ == '__main__':
    main()
