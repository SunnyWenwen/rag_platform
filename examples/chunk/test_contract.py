"""Run offline Chunk/Inference draft conformance checks; no models or DBs."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import unittest

from jsonschema import Draft202012Validator

from build_examples import build_cases
from contract import (ROOT, chunk_id, fingerprint, local_registry, validate_chunk,
                      validate_sequence, validate_spec)

HERE = Path(__file__).parent
CASES = build_cases()
BY_ID = {case['case_id']: case for case in CASES}


class ContractTests(unittest.TestCase):
    def test_canonical_examples_are_current(self):
        self.assertEqual(json.loads((HERE / 'cases.json').read_text()), CASES)

    def test_positive_chunks_and_sources(self):
        validate_document = runpy.run_path(str(ROOT / 'examples/parsed_document/validate.py'))['validate_document']
        for case in CASES:
            with self.subTest(case=case['case_id']):
                validate_document(case['source'])
                for chunk in case['chunks']:
                    validate_chunk(chunk, source=case['source'], effective_spec=case['effective_spec'],
                                   vector_bindings=case.get('vector_bindings'), require_provenance=True,
                                   require_empty_vectors=case['case_id'] != 'embedded')
                if case['case_id'] != 'embedded':
                    validate_sequence(case['chunks'], case['effective_spec'], case['source'])

    def test_two_plus_three_and_full_copies(self):
        case = BY_ID['two_plus_three']
        self.assertEqual(len(case['chunks']), 5)
        self.assertEqual([c['metadata']['_rag']['chunking']['chunk_ordinal'] for c in case['chunks']], list(range(5)))
        for chunk in case['chunks'][:2]:
            self.assertEqual(chunk['fields']['original_faq'], case['source']['units'][0]['faq'])
        for chunk in case['chunks'][2:]:
            self.assertEqual(chunk['fields']['original_text'], case['source']['units'][0]['text'])
        self.assertEqual([c['fields']['text'] for c in case['chunks']],
                         ['甲段。', '乙段。', '問一。', '問二。', '問三。'])

    def test_default_has_no_implicit_copies(self):
        self.assertEqual(set(BY_ID['default_text']['chunks'][0]['fields']), {'text'})

    def test_fingerprint_and_id_are_repeatable(self):
        case = BY_ID['default_text']
        spec = case['effective_spec']
        reordered = dict(reversed(list(spec.items())))
        self.assertEqual(fingerprint(spec), fingerprint(reordered))
        changed = deepcopy(spec)
        changed['tasks'][0]['parameters']['chunk_size'] += 1
        self.assertNotEqual(fingerprint(spec), fingerprint(changed))
        base = chunk_id('doc', 'v1', fingerprint(spec), 0)
        for args in [('doc', 'v2', fingerprint(spec), 0),
                     ('doc', 'v1', fingerprint(changed), 0),
                     ('doc', 'v1', fingerprint(spec), 1)]:
            self.assertNotEqual(base, chunk_id(*args))

    def test_copy_is_independent_data(self):
        case = deepcopy(BY_ID['copy_original'])
        original = deepcopy(case['source'])
        case['chunks'][0]['fields']['title'] = 'changed'
        self.assertEqual(case['source'], original)

    def test_existing_inference_examples_use_same_chunk_schema(self):
        schema = json.loads((ROOT / 'schemas/inference_context.schema.json').read_text())
        validator = Draft202012Validator(schema, registry=local_registry())
        paths = sorted((ROOT / 'examples/inference').glob('*.json'))
        self.assertEqual(len(paths), 5)
        for path in paths:
            state = json.loads(path.read_text())
            validator.validate(state)
            for query in state['query_contexts']:
                for result in query['result_sets']:
                    for item in result['items']:
                        validate_chunk(item['chunk'])
        # A nonempty modern vector reaches Inference through the same ref.
        state = json.loads(paths[0].read_text())
        state['query_contexts'][0]['result_sets'][0]['items'][0]['chunk'] = BY_ID['embedded']['chunks'][0]
        validator.validate(state)

    def test_invalid_chunks(self):
        negative = []

        def reject(name, mutate, *, case_id='default_text', **kwargs):
            case = deepcopy(BY_ID[case_id])
            chunk = case['chunks'][0]
            mutate(chunk)
            with self.subTest(case=name), self.assertRaises(Exception):
                validate_chunk(chunk, source=case['source'], effective_spec=case['effective_spec'],
                               vector_bindings=case.get('vector_bindings'), require_provenance=True,
                               require_empty_vectors=case_id != 'embedded', **kwargs)
            negative.append(name)

        reject('unknown root key', lambda c: c.update(structure={}))
        reject('missing key', lambda c: c.pop('vectors'))
        reject('empty fields', lambda c: c.update(fields={}))
        reject('missing provenance', lambda c: c.update(metadata={'department': 'engineering'}))
        reject('wrong document', lambda c: c.update(document_id='another'))
        reject('wrong revision', lambda c: c.update(source_revision='v2'))
        reject('business metadata removed', lambda c: c['metadata'].pop('department'))
        reject('wrong ID', lambda c: c.update(chunk_id='incorrect'))
        reject('wrong digest', lambda c: c['metadata']['_rag']['chunking'].update(chunking_fingerprint='0' * 64))
        reject('negative ordinal', lambda c: c['metadata']['_rag']['chunking'].update(chunk_ordinal=-1))
        reject('unknown task', lambda c: c['metadata']['_rag']['chunking'].update(task_id='unknown'))
        reject('empty refs', lambda c: c['metadata']['_rag'].update(source_refs=[]))
        reject('unknown source field', lambda c: c['metadata']['_rag']['source_refs'][0].update(field='missing'))
        reject('unknown output field', lambda c: c['metadata']['_rag']['source_refs'][0].update(output_field='missing'))
        reject('out of bounds', lambda c: c['metadata']['_rag']['source_refs'][0].update(end=999))
        reject('empty source slice', lambda c: c['metadata']['_rag']['source_refs'][0].update(end=5))
        reject('half range', lambda c: c['metadata']['_rag']['source_refs'][0].pop('end'))
        reject('changed output', lambda c: c['fields'].update(text='different'))
        reject('unconfigured field', lambda c: c['fields'].update(extra='unexpected'))
        reject('changed copy', lambda c: c['fields'].update(original_text='different'), case_id='copy_original')
        reject('copy selector is not full field', lambda c: c['metadata']['_rag']['source_refs'][1].update(start=0, end=1), case_id='copy_original')
        reject('old vector array', lambda c: c['vectors'].update(text=[0.1]), case_id='embedded')
        reject('unknown profile', lambda c: c['vectors']['text'].update(embedding_profile_id='other'), case_id='embedded')
        reject('wrong dimension', lambda c: c['vectors']['text'].update(values=[0.1]), case_id='embedded')
        reject('missing vector source', lambda c: c['vectors']['text'].update(source_field='missing'), case_id='embedded')
        reject('empty vector', lambda c: c['vectors']['text'].update(values=[]), case_id='embedded')
        reject('NaN vector', lambda c: c['vectors']['text'].update(values=[float('nan'), 0, 0]), case_id='embedded')
        reject('infinite metadata', lambda c: c['metadata'].update(bad=float('inf')))
        self.assertEqual(len(negative), 28)

    def test_invalid_sequences_and_mappings(self):
        case = BY_ID['two_plus_three']
        bad = deepcopy(case['chunks'])
        bad[1] = deepcopy(bad[0])
        with self.assertRaises(ValueError):
            validate_sequence(bad, case['effective_spec'])
        bad = deepcopy(case['chunks'])
        bad.reverse()
        with self.assertRaises(ValueError):
            validate_sequence(bad, case['effective_spec'])
        bad_spec = deepcopy(BY_ID['copy_original']['effective_spec'])
        bad_spec['tasks'][0]['copy_fields'][0]['output_field'] = 'text'
        with self.assertRaises(ValueError):
            validate_spec(bad_spec)
        bad_spec = deepcopy(case['effective_spec'])
        bad_spec['tasks'][1]['task_id'] = 'text'
        with self.assertRaises(ValueError):
            validate_spec(bad_spec)
        with self.assertRaisesRegex(ValueError, 'each required task'):
            validate_sequence(case['chunks'][:2], case['effective_spec'])


"""Contract checks for flat units; fixtures use supplied slices, not a tokenizer."""
from copy import deepcopy
from jsonschema import ValidationError
from build_examples import build_cases
from contract import validate_chunk, validate_sequence
cases=build_cases()
for case in cases:
    for chunk in case['chunks']:
        validate_chunk(chunk, source=case['source'], effective_spec=case['effective_spec'],
                       vector_bindings=case.get('vector_bindings'), require_provenance=True,
                       require_empty_vectors=case['case_id'] != 'embedded')
    if case['case_id'] != 'embedded': validate_sequence(case['chunks'],case['effective_spec'],case['source'])
case=next(c for c in cases if c['case_id']=='independent_units')
assert len(case['chunks'])==5
assert [c['metadata']['_rag']['source_refs'][0]['unit_index'] for c in case['chunks']]==[0,0,1,1,1]
checks=0
def reject(fn):
    global checks
    try: fn()
    except (ValueError,ValidationError): checks+=1
    else: raise AssertionError('invalid example accepted')
for change in ('missing_unit','out_of_range','wrong_unit','wrong_range','cross_unit','old_block','metadata','id'):
    c=deepcopy(case['chunks'][0]); ref=c['metadata']['_rag']['source_refs'][0]
    if change=='missing_unit': del ref['unit_index']
    elif change=='out_of_range': ref['unit_index']=10
    elif change=='wrong_unit': ref['unit_index']=1
    elif change=='wrong_range': ref['end']=100
    elif change=='cross_unit': c['metadata']['_rag']['source_refs'][1]['unit_index']=1
    elif change=='old_block': ref['block_id']='b1'
    elif change=='metadata': c['metadata']['extra']='not inherited'
    else: c['chunk_id']='bad'
    reject(lambda:validate_chunk(c,source=case['source'],effective_spec=case['effective_spec'],require_provenance=True))
reject(lambda:validate_sequence(case['chunks'][:2],case['effective_spec'],case['source']))
reject(lambda:validate_sequence(list(reversed(case['chunks'])),case['effective_spec'],case['source']))
for change in ('blank','missing_copy','wrong_type'):
    src=deepcopy(case['source'])
    if change=='blank': src['units'][1]['text']=' '
    elif change=='missing_copy': del src['units'][1]['page']
    else: src['units'][1]['text']=1
    reject(lambda:validate_chunk(case['chunks'][0],source=src,effective_spec=case['effective_spec']))
print(f'Chunk: {len(cases)} cases, {checks} negative checks passed')

if __name__ == '__main__':
    unittest.main(verbosity=2)
