"""Offline discussion fixtures, NOT the Engine compiler or final Descriptor schema.

Checks the proposed common shape, fixture component config_schema, and a bounded
set of assembly constraints. Never imports components or calls external services.
"""
from copy import deepcopy
from pathlib import Path
import json
import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / 'system_config.schema.json').read_text())
CATALOG = json.loads((HERE / 'catalog.fixture.json').read_text())
CATALOG_BY_KEY = {(d['component_id'], d['implementation_version']): d for d in CATALOG['components']}
ORDER = {'ingestion': ['import', 'parsing', 'chunking', 'embedding', 'indexing'],
         'inference': ['query_transformation', 'retrieval', 'rerank']}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selected(config):
    """Yield a selected implementation once; profiles/tasks are runtime choices."""
    for pipeline_name, pipeline in config['pipelines'].items():
        for module in ORDER[pipeline_name]:
            if module not in pipeline:
                continue
            value = pipeline[module]
            if module == 'parsing':
                for component in value['profiles'].values():
                    yield pipeline_name, module, component
            elif module == 'chunking':
                for task in value['tasks']:
                    yield pipeline_name, module, task['component']
            else:
                yield pipeline_name, module, value
        for component in pipeline.get('segments', []):
            yield pipeline_name, None, component


def validate(config, environment=None):
    json.dumps(config, allow_nan=False)
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator(SCHEMA).validate(config)
    for schema in config['document_schema'].values():
        Draft202012Validator.check_schema(schema)
        require(schema.get('type') == 'object', 'document schemas must describe objects')
    descriptors = []
    for pipeline, module, component in selected(config):
        key = component['component_id'], component['implementation_version']
        require(key in CATALOG_BY_KEY, 'unregistered fixture component/version: ' + str(key))
        descriptor = CATALOG_BY_KEY[key]
        require(descriptor['pipeline'] == pipeline, 'wrong pipeline')
        require(module is None or descriptor['modules'] == [module], 'wrong module/segment placement')
        Draft202012Validator(descriptor['config_schema']).validate(component.get('parameters', {}))
        descriptors.append((pipeline, module, component, descriptor))
        if environment is not None:
            if descriptor.get('remote'):
                require('@'.join(key) in environment.get('remote_bindings', {}), 'missing remote binding')
            service = component.get('parameters', {}).get('service_ref')
            if service:
                require(service in environment.get('service_bindings', {}), 'missing service binding')
    for name, pipeline in config['pipelines'].items():
        owned = set(pipeline) & set(ORDER[name])
        for component in pipeline.get('segments', []):
            descriptor = CATALOG_BY_KEY[(component['component_id'], component['implementation_version'])]
            positions = [ORDER[name].index(m) for m in descriptor['modules']]
            require(positions == list(range(min(positions), max(positions) + 1)), 'segment must be contiguous')
            require(not owned.intersection(descriptor['modules']), 'overlapping segment/module')
            owned.update(descriptor['modules'])
        mandatory = {'parsing', 'chunking', 'indexing'} if name == 'ingestion' else {'retrieval'}
        require(mandatory <= owned, 'missing mandatory module coverage')
    ingest, infer = config['pipelines']['ingestion'], config['pipelines']['inference']
    if 'parsing' in ingest:
        profiles = ingest['parsing']['profiles']
        default = ingest['parsing'].get('default_profile')
        require(default is None or default in profiles, 'invalid default parser profile')
    unit_fields = config['document_schema']['unit_schema'].get('properties', {})
    common_fields = None
    vectors = {}
    if 'chunking' in ingest:
        tasks = ingest['chunking']['tasks']
        require(len({t['task_id'] for t in tasks}) == len(tasks), 'duplicate task_id')
        for task in tasks:
            p = task['component']['parameters']
            require(p['overlap_tokens'] < p['max_tokens'], 'overlap must be smaller than max_tokens')
            require(p['tokenizer_profile_id'] in CATALOG['profiles'], 'unknown tokenizer profile')
            require(unit_fields.get(p['split_field'], {}).get('type') == 'string', 'undeclared/non-text split field')
            fields = [p['output_field']]
            for copy in p.get('copy_fields', []):
                require(copy['source_field'] in unit_fields, 'undeclared copy source')
                fields.append(copy['output_field'])
            require(len(fields) == len(set(fields)), 'conflicting output/copy field')
            common_fields = set(fields) if common_fields is None else common_fields & set(fields)
    for _, module, _, descriptor in descriptors:
        if module is None and descriptor.get('output_fields'):
            common_fields = set(descriptor['output_fields'])
            vectors.update(descriptor.get('vector_outputs', {}))
    common_fields = common_fields or set()
    if 'embedding' in ingest:
        p = ingest['embedding']['parameters']
        require(CATALOG['profiles'].get(p['profile_id'], {}).get('kind') == 'embedding', 'unknown embedding profile')
        for template in p.get('field_templates', []):
            source = template['template']
            references = re.findall(r'\{\{fields\.([^{}]+)\}\}', source)
            require(all(f in common_fields for f in references), 'template references unavailable field')
            remaining = re.sub(r'\{\{fields\.[^{}]+\}\}', '', source)
            require('{{' not in remaining and '}}' not in remaining, 'unsupported template syntax')
            require(template['output_field'] not in common_fields, 'template output conflicts')
            common_fields.add(template['output_field'])
        for mapping in p['mappings']:
            require(mapping['source_field'] in common_fields, 'embedding source unavailable')
            require(mapping['output_name'] not in vectors, 'duplicate vector output')
            vectors[mapping['output_name']] = p['profile_id']
    index_selection = ingest['indexing']  # These fixtures keep Indexing local.
    index_descriptor = CATALOG_BY_KEY[(index_selection['component_id'], index_selection['implementation_version'])]
    index = index_selection['parameters']
    for field in index['fulltext_fields']:
        require(field.startswith('fields.') and field[7:] in common_fields, 'index text unavailable')
    for field in index['vector_fields']:
        require(field.startswith('vectors.') and field[8:] in vectors, 'index vector unavailable')
    for field in index['filter_fields']:
        require(field.startswith('metadata.') and field[9:] in config['document_schema']['metadata_schema'].get('properties', {}), 'filter field undeclared')
    retrieval_selection = infer['retrieval']
    retrieval_descriptor = CATALOG_BY_KEY[(retrieval_selection['component_id'], retrieval_selection['implementation_version'])]
    require(index_descriptor['artifact_type'] in retrieval_descriptor.get('supports_artifacts', []), 'incompatible index/retrieval format')
    retrieval = retrieval_selection['parameters']
    if 'routes' in retrieval:
        routes = retrieval['routes']
        require(len({r['key'] for r in routes}) == len(routes), 'duplicate result key')
        for route in routes:
            allowed = index['fulltext_fields'] if route['kind'] == 'fulltext' else index['vector_fields']
            require(route['field'] in allowed, 'retrieval field is not indexed')
    else:
        require(set(retrieval['fulltext_fields']) <= set(index['fulltext_fields']), 'unindexed ES text')
        require(set(retrieval['vector_fields']) <= set(index['vector_fields']), 'unindexed ES vector')
    for name, llm in config.get('llms', {}).items():
        require(CATALOG['profiles'].get(llm['profile_id'], {}).get('kind') == 'llm', 'unknown LLM profile')
        if environment is not None:
            require(llm['service_ref'] in environment.get('service_bindings', {}), 'missing LLM binding')
    if 'query_transformation' in infer:
        require(infer['query_transformation']['parameters']['llm_ref'] in config.get('llms', {}), 'unknown llm_ref')
    if 'rerank' in infer:
        field = infer['rerank']['parameters']['content_field']
        require(field.startswith('fields.') and field[7:] in common_fields, 'rerank field unavailable')
    processing = infer.get('processing', {})
    for layer in ['same_query', 'cross_query']:
        if processing.get(layer, {}).get('enabled'):
            fusion = processing[layer]['fusion']
            require(fusion['method'] == 'rrf', 'fixture validator only covers RRF; Sum Score comparability requires an adapter')
            k = fusion.get('parameters', {}).get('k', 60)
            require(type(k) is int and k > 0, 'RRF k must be a positive integer')
    if 'after_rerank' in processing.get('top_n', {}):
        require('rerank' in infer, 'rerank retention requires an enabled reranker')
    return True


def run():
    environment = json.loads((HERE / 'environment.example.json').read_text())
    names = ['local_memory', 'remote_parser', 'remote_segment', 'advanced_fields', 'es_hybrid']
    examples = {name: json.loads((HERE / (name + '.json')).read_text()) for name in names}
    for config in examples.values():
        validate(config, environment)
    negatives = []

    def negative(name, edit, base='local_memory'):
        value = deepcopy(examples[base])
        edit(value)
        try:
            validate(value, environment)
        except (ValueError, ValidationError) as exc:
            negatives.append((name, type(exc).__name__))
            return
        raise AssertionError('accepted invalid config: ' + name)

    negative('unknown_root', lambda c: c.update({'runtime_settings': {}}))
    negative('unknown_component_version', lambda c: c['pipelines']['ingestion']['indexing'].update({'implementation_version': 'latest'}))
    negative('unknown_component_parameter', lambda c: c['pipelines']['ingestion']['indexing']['parameters'].update({'stored_fields': []}))
    negative('bad_chunk_overlap', lambda c: c['pipelines']['ingestion']['chunking']['tasks'][0]['component']['parameters'].update({'overlap_tokens': 500}))
    negative('missing_parser', lambda c: c['pipelines']['ingestion'].pop('parsing'))
    negative('overlapping_remote_segment', lambda c: c['pipelines']['ingestion'].update({'segments': [deepcopy(examples['remote_segment']['pipelines']['ingestion']['segments'][0])]}))
    negative('undeclared_split_field', lambda c: c['pipelines']['ingestion']['chunking']['tasks'][0]['component']['parameters'].update({'split_field': 'absent'}))
    negative('missing_embedding_source', lambda c: c['pipelines']['ingestion']['embedding']['parameters']['mappings'][0].update({'source_field': 'absent'}))
    negative('unindexed_retrieval_field', lambda c: c['pipelines']['inference']['retrieval']['parameters']['routes'][0].update({'field': 'fields.absent'}))
    negative('wrong_index_format', lambda c: c['pipelines']['inference'].update({'retrieval': deepcopy(examples['es_hybrid']['pipelines']['inference']['retrieval'])}))
    negative('unknown_llm', lambda c: c['pipelines']['inference']['query_transformation']['parameters'].update({'llm_ref': 'absent'}), 'advanced_fields')
    negative('template_source_missing', lambda c: c['pipelines']['ingestion']['embedding']['parameters']['field_templates'][0].update({'template': '{{fields.absent}}'}), 'advanced_fields')
    negative('template_conflict', lambda c: c['pipelines']['ingestion']['embedding']['parameters']['field_templates'][0].update({'output_field': 'text'}), 'advanced_fields')
    negative('rerank_disabled_but_retention_present', lambda c: c['pipelines']['inference']['processing']['top_n'].update({'after_rerank': 3}))
    negative('data_space_id', lambda c: c.update({'data_space_id': 'x'}))
    negative('generation', lambda c: c['pipelines']['inference'].update({'generation': {}}))
    negative('query_state_in_config', lambda c: c.update({'result_sets': []}))
    negative('duplicate_task_id', lambda c: c['pipelines']['ingestion']['chunking']['tasks'].append(deepcopy(c['pipelines']['ingestion']['chunking']['tasks'][0])))
    missing_environment = deepcopy(environment)
    missing_environment['service_bindings'].pop('embedding.main')
    try:
        validate(examples['local_memory'], missing_environment)
    except ValueError:
        negatives.append(('missing_environment_binding', 'ValueError'))
    else:
        raise AssertionError('accepted missing E binding')
    print(json.dumps({'positive_configs': len(examples), 'negative_configs': len(negatives),
                      'checks': ['base schema', 'fixture config_schema', 'coverage', 'field/vector refs', 'format pairing', 'E refs'],
                      'not_checked': ['real implementations', 'model APIs', 'index writes', 'full metadata/UI meta-schema', 'all backend score policies']}, ensure_ascii=False))


if __name__ == '__main__':
    run()
