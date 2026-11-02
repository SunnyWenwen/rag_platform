"""Export a $defs catalog; it is not a root payload validation schema."""
import json
from pathlib import Path
from pydantic.json_schema import models_json_schema
from models import PUBLIC_MODELS, ModuleResult, InferenceState


def main():
    models=PUBLIC_MODELS+[ModuleResult[InferenceState]]
    _, schema=models_json_schema([(m,'validation') for m in models],title='Diagram 03 — Pydantic contract draft')
    schema['$schema']='https://json-schema.org/draft/2020-12/schema'
    schema['description']='Draft type catalog. IndexBinding fields are proposed. Pydantic custom semantic validators are not all represented here; existing shared schemas remain authoritative.'
    path=Path(__file__).with_name('pydantic_contracts.schema.json')
    path.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')
    print(f'Exported {len(schema["$defs"])} definitions to {path.name}')


if __name__=='__main__':main()
