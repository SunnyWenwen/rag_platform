"""Offline checks against existing shared fixtures and canonical JSON Schemas."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from pydantic import ValidationError, TypeAdapter
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
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
    return IndexBinding(artifact_type='builtin.elasticsearch/v1',target={'collection':'ws-system-a'},
        fulltext_fields=['fields.text'],filter_fields=[],
        vector_bindings={'text':VectorIndexBinding(embedding_profile_id='embedding-demo-v1',source_field='text',dimensions=3)})



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
            result=[q.to_payload() for q in TypeAdapter(list[QueryContext]).validate_python(state)];infer.validate(result);self.assertEqual(result,state)
            for query in TypeAdapter(list[QueryContext]).validate_python(state):
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

    def test_current_result_contract(self):
        rs=ResultSet.model_validate(STATES[0][0]['result_sets'][0])
        rank_only=ResultSet(key='rank_only',items=[ResultItem(chunk=rs.items[0].chunk)])
        validate_result_order(rank_only)
        with self.assertRaises(ValueError):require_sum_scores([rank_only])
        require_sum_scores([rs])
        with self.assertRaises(ValidationError):ResultItem(chunk=rs.items[0].chunk,score=float('nan'))
        for stale in ('rank','source_refs'):
            with self.assertRaises(ValidationError):ResultItem.model_validate({**rs.items[0].to_payload(),stale:1})
        with self.assertRaises(ValidationError):ResultSet.model_validate({**rs.to_payload(),'stage':'retrieval'})
        with self.assertRaises(ValidationError):QueryContext(ori_query='q',query='q',result_sets=[rs,rs])
        with self.assertRaises(ValidationError):TypeAdapter(list[QueryContext]).validate_python({'query_contexts':STATES[0]})
        self.assertEqual(TypeAdapter(list[QueryContext]).validate_python([]),[])

    def test_filters_and_metadata(self):
        for op,value in [('eq','製造部'),('in',['製造部','研發'])]:
            condition=FilterCondition(field='metadata.department',operator=op,value=value)
            q=QueryContext(ori_query='q',query='q',filters=[condition],metadata={'language':'zh-TW','nested':{'a':1}})
            self.assertEqual(q.filters[0].value,value)
        for op,value in [('eq',[]),('in','x'),('in',[]),('gt','1')]:
            with self.assertRaises(ValidationError):FilterCondition(field='x',operator=op,value=value)
        with self.assertRaises(ValueError):QueryContext(ori_query='q',query='q',metadata={'x':float('inf')})
        q=QueryContext(ori_query='q',query='q')
        self.assertEqual((q.filters,q.result_sets,q.metadata),([],[],{}))

    def test_index_binding_and_vectors(self):
        target=binding();embedded=Chunk.model_validate(next(c for c in CASES if c['case_id']=='embedded')['chunks'][0])
        validate_chunk_binding(embedded,target)
        target.vector_bindings['text'].dimensions=4
        with self.assertRaises(ValueError):validate_chunk_binding(embedded,target)
        value=binding().to_payload();value['index_ref']='removed'
        with self.assertRaises(ValidationError):IndexBinding.model_validate(value)
        value=binding().to_payload();value['password']='not allowed'
        with self.assertRaises(ValidationError):IndexBinding.model_validate(value)

    def test_new_examples_are_valid_wire_payloads(self):
        examples=json.loads(Path(__file__).with_name('examples.json').read_text())
        for name,schema_name in [('ingestion_document','ingestion_document'),('chunk_after_chunking','chunk'),('chunk_after_embedding','chunk'),('query_contexts','inference_context')]:
            schema=json.loads((ROOT/'schemas'/f'{schema_name}.schema.json').read_text())
            Draft202012Validator(schema,registry=registry()).validate(examples[name])
        for doc in examples['parsed_documents']:
            ParsedDocument.model_validate(doc)
        validate_chunk_binding(Chunk.model_validate(examples['chunk_after_embedding']),IndexBinding.model_validate(examples['index_binding']))

    def test_each_public_type_has_an_executable_example(self):
        from typed_examples import TYPE_EXAMPLES, chunk, chunks, rag_metadata, parsed_doc, index_binding, query_contexts
        self.assertEqual(set(TYPE_EXAMPLES), {model.__name__ for model in PUBLIC_MODELS} | {'ModuleResult'})
        snapshots=json.loads(Path(__file__).with_name('examples.json').read_text())['type_examples']
        for name, value in TYPE_EXAMPLES.items():
            with self.subTest(type=name):
                payload=value.to_payload()
                self.assertEqual(type(value).model_validate_json(json.dumps(payload)).to_payload(), payload)
                self.assertEqual(snapshots[name],payload)
        for name, schema_name in [('IngestionDocument','ingestion_document'), ('ParsedDocument','parsed_document'),
                                  ('Chunk','chunk')]:
            schema=json.loads((ROOT/'schemas'/f'{schema_name}.schema.json').read_text())
            Draft202012Validator(schema,registry=registry()).validate(snapshots[name])
        embedded=Chunk.model_validate({**chunk.to_payload(),'vectors':{'text':TYPE_EXAMPLES['DenseVector'].to_payload()}})
        validate_chunk_binding(embedded,index_binding)
        for context in query_contexts:
            for rs in context.result_sets:validate_result_order(rs)
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

    def test_binding_registration_target_and_retrieval_pairing(self):
        es=binding();validate_binding_format(es,['builtin.elasticsearch/v1'])
        with self.assertRaises(ValueError):validate_binding_format(es,['builtin.local_search/v1'])
        es.target={}
        with self.assertRaises(ValidationError):validate_binding_format(es,['builtin.elasticsearch/v1'])
        local=IndexBinding(artifact_type='builtin.local_search/v1')
        validate_binding_format(local,['builtin.local_search/v1'])
        local.target={'es_client':'not a location'}
        with self.assertRaises(ValidationError):validate_binding_format(local,['builtin.local_search/v1'])
        from pydantic import Field
        class CustomTarget(WireModel):
            dataset: NonEmptyText
        custom=IndexBinding(artifact_type='developer.custom/v1',target={'dataset':'docs'})
        with self.assertRaises(ValueError):validate_binding_format(custom,['developer.custom/v1'])
        validate_binding_format(custom,['developer.custom/v1'],{'developer.custom/v1':CustomTarget})
        with self.assertRaises(ValidationError):IndexBinding.model_validate({**binding().to_payload(),'searchable':True})
        self.assertEqual(IndexBinding(artifact_type='builtin.local_search/v1').target,{})

    def test_retrieval_requires_declared_fields(self):
        target=binding()
        validate_retrieval_fields(target,fulltext_fields=['fields.text'],vector_names=['text'])
        for arguments in ({'fulltext_fields':['fields.summary']},
                          {'vector_names':['summary']}, {'filter_fields':['metadata.department']}):
            with self.assertRaises(ValueError):validate_retrieval_fields(target,**arguments)

    def test_standalone_binding_schema_and_artifact_definitions(self):
        from typed_examples import index_binding
        schema=json.loads((ROOT/'schemas/index_binding.schema.json').read_text())
        validator=Draft202012Validator(schema)
        validator.validate(index_binding.to_payload())
        for removed in ('index_ref','searchable','capabilities'):
            with self.assertRaises(SchemaValidationError):validator.validate({**index_binding.to_payload(),removed:'old'})
        definitions=json.loads(Path(__file__).with_name('artifact_definitions.json').read_text())
        by_type={d['artifact_type']:d['target_schema'] for d in definitions}
        Draft202012Validator(by_type[index_binding.artifact_type]).validate(index_binding.target)
        Draft202012Validator(by_type['builtin.local_search/v1']).validate({})
        with self.assertRaises(SchemaValidationError):Draft202012Validator(by_type['builtin.elasticsearch/v1']).validate({})

    def test_generated_catalog_and_module_result(self):
        from pydantic.json_schema import models_json_schema
        _,schema=models_json_schema([(m,'validation') for m in PUBLIC_MODELS])
        Draft202012Validator.check_schema(schema)
        self.assertIn('IndexBinding',schema['$defs'])
        from typed_examples import parsed_doc
        wrapped=ModuleResult[list[ParsedDocument]](data=[parsed_doc])
        self.assertEqual(wrapped.to_payload()['data'],[parsed_doc.to_payload()])

    def test_reference_operations_use_positions_and_current_data(self):
        import runpy
        ops=runpy.run_path(str(ROOT/'examples/inference/python_example.py'))
        q=deepcopy(STATES[0][0]);rs=q['result_sets'][0]
        for item in rs['items']:item.pop('score',None)
        fused=ops['rrf']([rs])
        self.assertAlmostEqual(fused['items'][0]['score'],1/61)
        self.assertEqual(set(fused),{'key','items'})
        same=ops['same_query_merge'](q,1)
        self.assertEqual(len(same['result_sets']),1)
        self.assertEqual(len(same['result_sets'][0]['items']),1)
        rewritten=deepcopy(same);rewritten['query']='改寫'
        combined=ops['cross_query_merge']([same,rewritten],3)
        self.assertEqual(combined[0]['query'],q['ori_query'])
        rewritten['metadata']={'language':'en'}
        with self.assertRaises(ValueError):ops['cross_query_merge']([same,rewritten],3)



if __name__=='__main__':unittest.main(verbosity=2)



