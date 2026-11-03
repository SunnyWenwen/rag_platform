"""Export a $defs catalog; it is not a root payload validation schema."""
import json
from pathlib import Path
from pydantic.json_schema import models_json_schema
from pydantic import TypeAdapter
from models import PUBLIC_MODELS, ModuleResult, ParsedDocument, QueryContext


def main():
    models=PUBLIC_MODELS+[ModuleResult[list[ParsedDocument]]]
    _, schema=models_json_schema([(m,'validation') for m in models],title='Diagram 03 — Pydantic contract draft')
    schema['$schema']='https://json-schema.org/draft/2020-12/schema'
    schema['description']='Draft type catalog. IndexBinding fields are proposed. Pydantic custom semantic validators are not all represented here; existing shared schemas remain authoritative.'
    path=Path(__file__).with_name('pydantic_contracts.schema.json')
    path.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')
    root = TypeAdapter(list[QueryContext]).json_schema()
    root.update({'$schema':'https://json-schema.org/draft/2020-12/schema',
                 '$id':'https://rag-builder.example.invalid/schemas/query-context-list-0.3-draft.schema.json',
                 'title':'QueryContext[] — current inference data',
                 'description':'Approved simplified inference contract. Breaking replacement of the old state wrapper; no historical result sets. Semantic checks also apply.'})
    root['$defs']['Chunk'] = {'$ref':'urn:rag-builder:chunk:0.2-draft'}
    # Keep only definitions actually reachable from QueryContext. Chunk is shared.
    reachable={'Chunk'}
    def visit(value):
        if isinstance(value,dict):
            ref=value.get('$ref','')
            if ref.startswith('#/$defs/'):
                name=ref.split('/')[-1]
                if name not in reachable:
                    reachable.add(name); visit(root['$defs'][name])
            for key,item in value.items():
                if key!='$defs': visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit({k:v for k,v in root.items() if k!='$defs'})
    root['$defs']={k:v for k,v in root['$defs'].items() if k in reachable}
    # JSON Schema expresses the operator/value dependency as well as Pydantic.
    root['$defs']['FilterCondition']['allOf']=[
        {'if':{'properties':{'operator':{'const':'eq'}}},'then':{'properties':{'value':{'type':'string'}}}},
        {'if':{'properties':{'operator':{'const':'in'}}},'then':{'properties':{'value':{'type':'array','minItems':1,'items':{'type':'string'}}}}}]
    (Path(__file__).resolve().parents[2]/'schemas/inference_context.schema.json').write_text(json.dumps(root,ensure_ascii=False,indent=2)+'\n')
    print(f'Exported {len(schema["$defs"])} definitions to {path.name}')


if __name__=='__main__':main()

