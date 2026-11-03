"""Offline checks against existing shared fixtures and canonical JSON Schemas."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from pydantic import ValidationError
from jsonschema import Draft202012Validator
from referencing import Registry,Resource
from models import *

ROOT=Path(__file__).resolve().parents[2]
CASES=json.loads((ROOT/'examples/chunk/cases.json').read_text())
STATES=[json.loads(p.read_text()) for p in sorted((ROOT/'examples/inference').glob('*.json'))]


def registry():
    reg=Registry()
    for path in (ROOT/'schemas').glob('*.json'):
        schema=json.loads(path.read_text())
        if '$id' in schema:reg=reg.with_resource(schema['$id'],Resource.from_contents(schema))
    return reg


def binding():
    return IndexBinding(contract_version='index-binding-0.1-proposal',index_ref='idx-demo',
        system_id='system-A',backend='elasticsearch',collection='ws-system-a',index_generation='g1',
        mapping_version='mapping-v1',document_schema_version='unit-schema-v1',
        capabilities=['fulltext','dense_vector'],fulltext_fields=['fields.text'],filter_fields=[],
        vector_bindings={'text':VectorIndexBinding(embedding_profile_id='embedding-demo-v1',source_field='text',dimensions=3)},searchable=True)


class ModelTests(unittest.TestCase):
    def test_existing_shared_fixtures_roundtrip(self):
        parsed=Draft202012Validator(json.loads((ROOT/'schemas/parsed_document.schema.json').read_text()))
        chunk=Draft202012Validator(json.loads((ROOT/'schemas/chunk.schema.json').read_text()),registry=registry())
        for case in CASES:
            source=ParsedDocument.model_validate(case['source']).to_payload();parsed.validate(source)
            self.assertEqual(source,case['source'])
            for data in case['chunks']:
                result=Chunk.model_validate(data).to_payload();chunk.validate(result);self.assertEqual(result,data)
        infer=Draft202012Validator(json.loads((ROOT/'schemas/inference_context.schema.json').read_text()),registry=registry())
        for state in STATES:
            result=InferenceState.model_validate(state).to_payload();infer.validate(result);self.assertEqual(result,state)
            for query in InferenceState.model_validate(state).query_contexts:
                for rs in query.result_sets:validate_result_order(rs)

    def test_input_sources_and_omission(self):
        schema=Draft202012Validator(json.loads((ROOT/'schemas/ingestion_document.schema.json').read_text()))
        for value in [{'document_id':'d','content':'text'}, {'document_id':'d','uri':'https://example.com/a'},
                      {'document_id':'d','base64':'dGV4dA=='}]:
            result=IngestionDocument.model_validate(value).to_payload();self.assertEqual(result,value);schema.validate(result)
        for value in [{'document_id':'d'}, {'document_id':'d','content':'text','uri':'https://example.com'},
                      {'document_id':'d','content':None}, {'document_id':'d','content':'text','source_revision':None},
                      {'document_id':'d','content':'text','unexpected':1}]:
            with self.assertRaises(ValidationError):IngestionDocument.model_validate(value)

    def test_units_remain_plain_dictionaries(self):
        value={'document_id':'d','source_revision':'v1','units':[{'text':'A','page':1},{'custom_text':'B'}],'metadata':{}}
        doc=ParsedDocument.model_validate(value)
        self.assertIsInstance(doc.units[0],dict)
        for units in [[],[{}],[{'text':1}]]:
            with self.assertRaises(ValidationError):ParsedDocument.model_validate({**value,'units':units})

    def test_chunk_provenance_and_finite_vectors(self):
        base=deepcopy(CASES[0]['chunks'][0]);ref=base['metadata']['_rag']['source_refs'][0]
        for updates in [{'unit_index':-1},{'start':4,'end':2},{'start':None},{'block_id':'old'}]:
            bad=deepcopy(base);bad['metadata']['_rag']['source_refs'][0].update(updates)
            with self.assertRaises(ValidationError):Chunk.model_validate(bad)
        for value in [float('nan'),float('inf')]:
            with self.assertRaises(ValidationError):DenseVector(values=[value],embedding_profile_id='p',source_field='text')
        with self.assertRaises(ValidationError):Chunk.model_validate({**base,'metadata':{'_rag':None}})
        self.assertNotIn('start',ChunkSourceRef(unit_index=0,field='text',output_field='text',role='copy').to_payload())
        with self.assertRaises(ValidationError):ChunkSourceRef(unit_index=0,field="text",output_field="original_text",role="copy",chunk_start=0,chunk_end=1)

    def test_resultset_stage_rules_and_lineage(self):
        first=deepcopy(STATES[0]['query_contexts'][0]['result_sets'][0])
        for change in ('source','inputs','lineage'):
            bad=deepcopy(first)
            if change=='source':bad['source']=None
            elif change=='inputs':bad['input_result_set_ids']=['rs-old']
            else:bad['items'][0]['source_refs']=[{'result_set_id':'old','chunk_id':'c'}]
            with self.assertRaises(ValidationError):ResultSet.model_validate(bad)
        later=deepcopy(first);later.update(stage='top_n',source=None,input_result_set_ids=['rs-old'])
        with self.assertRaises(ValidationError):ResultSet.model_validate(later)
        with self.assertRaises(ValidationError):Operation(method='x',parameters={},scoring_query_id=None)

    def test_active_references_and_rank(self):
        value=deepcopy(STATES[0]);value['active_query_ids']=['missing']
        with self.assertRaises(ValidationError):InferenceState.model_validate(value)
        value=deepcopy(STATES[0]['query_contexts'][0]);value['active_result_set_ids']=['missing']
        with self.assertRaises(ValidationError):QueryContext.model_validate(value)
        rs=ResultSet.model_validate(STATES[0]['query_contexts'][0]['result_sets'][0]);rs.items[0].rank=2
        with self.assertRaises(ValueError):validate_result_order(rs)

    def test_proposed_index_binding_and_vectors(self):
        target=binding();embedded=Chunk.model_validate(next(c for c in CASES if c['case_id']=='embedded')['chunks'][0])
        validate_chunk_binding(embedded,target)
        target.vector_bindings['text'].dimensions=4
        with self.assertRaises(ValueError):validate_chunk_binding(embedded,target)
        value=binding().to_payload();value['capabilities']=[]
        with self.assertRaises(ValidationError):IndexBinding.model_validate(value)
        value=binding().to_payload();value['password']='not allowed'
        with self.assertRaises(ValidationError):IndexBinding.model_validate(value)

    def test_new_examples_are_valid_wire_payloads(self):
        examples=json.loads(Path(__file__).with_name('examples.json').read_text())
        for name,schema_name in [('ingestion_document','ingestion_document'),('chunk_after_chunking','chunk'),('chunk_after_embedding','chunk'),('inference_state','inference_context')]:
            schema=json.loads((ROOT/'schemas'/f'{schema_name}.schema.json').read_text())
            Draft202012Validator(schema,registry=registry()).validate(examples[name])
        for doc in examples['parsed_documents']:
            ParsedDocument.model_validate(doc)
        validate_chunk_binding(Chunk.model_validate(examples['chunk_after_embedding']),IndexBinding.model_validate(examples['index_binding_PROPOSAL']))

    def test_each_public_type_has_an_executable_example(self):
        from typed_examples import TYPE_EXAMPLES, chunk, chunks, rag_metadata, parsed_doc, index_binding, inference_state
        self.assertEqual(set(TYPE_EXAMPLES), {model.__name__ for model in PUBLIC_MODELS} | {'ModuleResult'})
        snapshots=json.loads(Path(__file__).with_name('examples.json').read_text())['type_examples']
        for name, value in TYPE_EXAMPLES.items():
            with self.subTest(type=name):
                payload=value.to_payload()
                self.assertEqual(type(value).model_validate_json(json.dumps(payload)).to_payload(), payload)
                self.assertEqual(snapshots[name],payload)
        for name, schema_name in [('IngestionDocument','ingestion_document'), ('ParsedDocument','parsed_document'),
                                  ('Chunk','chunk'), ('InferenceState','inference_context')]:
            schema=json.loads((ROOT/'schemas'/f'{schema_name}.schema.json').read_text())
            Draft202012Validator(schema,registry=registry()).validate(snapshots[name])
        embedded=Chunk.model_validate({**chunk.to_payload(),'vectors':{'text':TYPE_EXAMPLES['DenseVector'].to_payload()}})
        validate_chunk_binding(embedded,index_binding)
        for context in inference_state.query_contexts:
            by_id={rs.result_set_id:rs for rs in context.result_sets}
            for rs in context.result_sets:
                validate_result_order(rs)
                for parent_id in rs.input_result_set_ids:self.assertIn(parent_id,by_id)
                for item in rs.items:
                    for ref in item.source_refs:
                        self.assertIn(ref.result_set_id,rs.input_result_set_ids)
                        self.assertIn(ref.chunk_id,{i.chunk.chunk_id for i in by_id[ref.result_set_id].items})
        for ref in rag_metadata.to_payload()['source_refs']:
            original=parsed_doc.units[ref['unit_index']][ref['field']]
            expected=original[ref['start']:ref['end']] if ref['role']=='split' else original
            self.assertEqual(chunk.fields[ref['output_field']],expected)

    def test_ten_character_demo_produces_three_chunks(self):
        from typed_examples import chunks, parsed_doc, ingestion_doc
        self.assertEqual(len(parsed_doc.units[1]['text']),15)
        self.assertIn(parsed_doc.units[1]['text'], ingestion_doc.content['text'])
        self.assertEqual([c.fields['text'] for c in chunks],['清潔前先斷電。','每月清潔散熱孔並檢查','風扇運轉。'])
        self.assertEqual([len(c.fields['text']) for c in chunks],[7,10,5])
        self.assertEqual([c.fields['page'] for c in chunks],[1,2,2])
        self.assertEqual(len({c.chunk_id for c in chunks}),3)
        for unit in parsed_doc.units:
            self.assertEqual(''.join(c.fields['text'] for c in chunks if c.fields['page']==unit['page']),unit['text'])
        for chunk in chunks:
            self.assertEqual(chunk.metadata,parsed_doc.metadata)
            self.assertNotIn('_rag',chunk.metadata)
            self.assertEqual(chunk.vectors,{})
            self.assertEqual(chunk.document_id,parsed_doc.document_id)
            self.assertEqual(chunk.source_revision,parsed_doc.source_revision)
            self.assertEqual(chunk.fields['title'],parsed_doc.units[0]['title'])
        snapshot=json.loads(Path(__file__).with_name('examples.json').read_text())
        self.assertEqual(snapshot['ten_character_chunk_demo'],[c.to_payload() for c in chunks])

    def test_generated_catalog_and_module_result(self):
        from pydantic.json_schema import models_json_schema
        _,schema=models_json_schema([(m,'validation') for m in PUBLIC_MODELS])
        Draft202012Validator.check_schema(schema)
        self.assertIn('IndexBinding',schema['$defs'])
        state=InferenceState.model_validate(STATES[0]);wrapped=ModuleResult[InferenceState](data=state)
        self.assertEqual(wrapped.to_payload()['data'],STATES[0])


if __name__=='__main__':unittest.main(verbosity=2)


