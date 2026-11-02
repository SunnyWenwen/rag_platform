"""Readable contract snapshots; supplied chunks/vectors are illustrative, not computed."""
from copy import deepcopy
import json
from pathlib import Path
from models import *
from typed_examples import TYPE_EXAMPLES

ROOT=Path(__file__).resolve().parents[2]


def main():
    data=IngestionDocument.model_validate(json.loads((ROOT/'examples/component_development/multi_page_input.json').read_text()))
    documents=[ParsedDocument.model_validate(d) for d in json.loads((ROOT/'examples/component_development/multi_page_output.json').read_text())]
    document=documents[0];unit=document.units[0];metadata=deepcopy(document.metadata)
    metadata['_rag']={'source_refs':[{'unit_index':0,'field':'text','output_field':'text','role':'split','start':0,'end':len(unit['text'])},
                                   {'unit_index':0,'field':'title','output_field':'title','role':'copy'},
                                   {'unit_index':0,'field':'page','output_field':'page','role':'copy'}],
                      'chunking':{'chunking_fingerprint':'0'*64,'chunk_ordinal':0,'task_id':'text'}}
    raw=Chunk(chunk_id='chunk-demo-001',document_id=document.document_id,source_revision=document.source_revision,
              fields=deepcopy(unit),metadata=metadata,vectors={})
    embedded=Chunk.model_validate({**raw.to_payload(),'vectors':{'text':{'values':[0.1,0.2,0.3],'embedding_profile_id':'embedding-demo-v1','source_field':'text'}}})
    binding=IndexBinding(contract_version='index-binding-0.1-proposal',index_ref='idx-demo',system_id='system-A',backend='elasticsearch',
        collection='ws-system-a',index_generation='g1',mapping_version='mapping-v1',document_schema_version='unit-schema-v1',
        capabilities=['fulltext','dense_vector'],fulltext_fields=['fields.text'],filter_fields=[],
        vector_bindings={'text':VectorIndexBinding(embedding_profile_id='embedding-demo-v1',source_field='text',dimensions=3)},searchable=True)
    validate_chunk_binding(embedded,binding)
    r1=ResultSet(result_set_id='rs-retrieval',stage='retrieval',input_result_set_ids=[],source=RetrievalSource(route_id='es-hybrid',index_ref='idx-demo',field_paths=['fields.text','vectors.text']),
        operation=Operation(method='es_sum_score',parameters={},model_ref=None,scoring_query_id=None),score_kind='es_sum_score',score_order='higher_is_better',
        items=[ResultItem(chunk=raw,score=0.83,rank=1,source_refs=[])])
    r2=ResultSet(result_set_id='rs-rerank',stage='model_score',input_result_set_ids=['rs-retrieval'],source=None,
        operation=Operation(method='cross_encoder',parameters={},model_ref='rerank-demo-v1',scoring_query_id='q-original'),score_kind='reranker_score',score_order='higher_is_better',
        items=[ResultItem(chunk=raw,score=0.95,rank=1,source_refs=[ResultSourceRef(result_set_id='rs-retrieval',chunk_id=raw.chunk_id)])])
    query=QueryContext(query_id='q-original',query='清潔前應注意什麼？',ori_query_id='q-original',ori_query='清潔前應注意什麼？',source_query_ids=[],result_sets=[r1,r2],active_result_set_ids=['rs-rerank'])
    state=InferenceState(contract_version='inference-0.2-draft',query_contexts=[query],active_query_ids=['q-original'])
    snapshots={'note':'Manually assembled contract examples. Chunk ID/fingerprint/vector/scores are illustrative; no tokenizer/model/index was executed.',
        'ingestion_document':data.to_payload(),'parsed_documents':[d.to_payload() for d in documents],
        'chunk_after_chunking':raw.to_payload(),'chunk_after_embedding':embedded.to_payload(),'index_binding_PROPOSAL':binding.to_payload(),
        'query_context':query.to_payload(),'inference_state':state.to_payload(),'module_result_success':ModuleResult[InferenceState](data=state).to_payload()}
    snapshots['type_examples'] = {name: value.to_payload() for name, value in TYPE_EXAMPLES.items()}
    Path(__file__).with_name('examples.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+'\n')
    print('Wrote examples.json: shared DTOs plus a separately marked IndexBinding proposal')


if __name__=='__main__':main()

