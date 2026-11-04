"""Readable contract snapshots; supplied chunks/vectors are illustrative, not computed."""
from copy import deepcopy
import json
from pathlib import Path
from models import *
from typed_examples import TYPE_EXAMPLES, chunks

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
    binding=IndexBinding(artifact_type='builtin.elasticsearch/v1',target={'collection':'ws-system-a'},
        fulltext_fields=['fields.text'],filter_fields=[],
        vector_bindings={'text':VectorIndexBinding(embedding_profile_id='embedding-demo-v1',source_field='text',dimensions=3)})
    validate_binding_format(binding,['builtin.elasticsearch/v1'])
    validate_chunk_binding(embedded,binding)
    query=QueryContext(ori_query='清潔前應注意什麼？',query='清潔前應注意什麼？',
        filters=[FilterCondition(field='metadata.department',operator='eq',value='製造部')],
        result_sets=[ResultSet(key='merged',items=[ResultItem(chunk=raw,score=0.95)])],metadata={'language':'zh-TW'})
    snapshots={'note':'Manually assembled contract examples. Chunk ID/fingerprint/vector/scores are illustrative; no tokenizer/model/index was executed.',
        'ingestion_document':data.to_payload(),'parsed_documents':[d.to_payload() for d in documents],
        'chunk_after_chunking':raw.to_payload(),'chunk_after_embedding':embedded.to_payload(),'index_binding':binding.to_payload(),
        'query_context':query.to_payload(),'query_contexts':[query.to_payload()],'module_result_success':ModuleResult[list[ParsedDocument]](data=documents).to_payload()}
    snapshots['ten_character_chunk_demo'] = [chunk.to_payload() for chunk in chunks]
    snapshots['type_examples'] = {name: value.to_payload() for name, value in TYPE_EXAMPLES.items()}
    Path(__file__).with_name('examples.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+'\n')
    print('Wrote examples.json: shared DTOs including the approved lightweight IndexBinding')


if __name__=='__main__':main()



