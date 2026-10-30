"""Download pinned official outputs and check reference adapter conformance.

Usage: python check_provider_samples.py --cache-dir /tmp/pd-fixtures
       --output-dir /tmp/pd-normalized --report /tmp/pd-report.json

Downloads fixture JSON only, never PDFs/models. URLs and SHA-256 values are
pinned in provider_cases.json. Downloaded native/normalized full documents are
not checked in. The report contains counts, outcomes and source provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import urllib.request

from provider_adapters import as_page_blocks, extension_registry, from_docling, from_mineru
from validate import validate_document


def verify_retention(native, normalized, provider):
    structure = normalized['structure']['text']
    blocks = structure.get('blocks', [b for p in structure.get('pages', []) for b in p['blocks']])
    reconstructed = deepcopy(normalized['metadata']['_rag']['native_document'])
    if provider == 'docling':
        collections = ('texts', 'tables', 'pictures', 'groups', 'key_value_items', 'form_items', 'field_regions', 'field_items')
        originals = [b['extensions']['source.docling'] for b in blocks]
        for collection in collections:
            if collection in native:
                items = [x for x in originals if x['self_ref'].startswith(f'#/{collection}/')]
                reconstructed[collection] = sorted(items, key=lambda x: int(x['self_ref'].rsplit('/', 1)[1]))
        for b in blocks:
            original = b['extensions']['source.docling']
            if original.get('text'):
                text = normalized['fields']['text'][b['start']:b['end']] if 'start' in b else b['text']
                assert text == original['text'], 'text not preserved'
            if b['type'] == 'table':
                assert normalized['fields'][b['data_ref']]['payload'] == original.get('data', {})
    else:
        pages = deepcopy(normalized['metadata']['_rag']['native_pages'])
        for page in pages:
            page['blocks'] = [b['extensions']['source.mineru'] for b in blocks if b['locations'][0]['page_number'] == page['page_idx'] + 1]
        reconstructed['pages'] = pages
        for b in blocks:
            original = b['extensions']['source.mineru']['content']
            expected = original if isinstance(original, str) else ''.join(s['content'] for s in original)
            actual = normalized['fields']['text'][b['start']:b['end']] if 'start' in b else b['text']
            assert actual == expected, 'inline text not preserved'
    assert reconstructed == native, 'native JSON reconstruction differs'


def run(cache_dir, output_dir):
    here = Path(__file__).parent
    cases = json.loads((here / 'provider_cases.json').read_text())
    cache_dir.mkdir(parents=True, exist_ok=True)
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for case in cases:
        cached = cache_dir / case['cache_name']
        if not cached.exists():
            with urllib.request.urlopen(case['url'], timeout=45) as response:
                cached.write_bytes(response.read())
        data = cached.read_bytes()
        assert hashlib.sha256(data).hexdigest() == case['sha256'], f'fixture hash mismatch: {case["id"]}'
        native = json.loads(data)
        source = {k: case[k] for k in ('url', 'sha256', 'revision', 'path')}
        adapter = from_docling if case['provider'] == 'docling' else from_mineru
        if case.get('expect_rejected'):
            try:
                adapter(native, case['url'])
            except ValueError as error:
                results.append({'id': case['id'], 'source': source, 'status': 'rejected_as_expected', 'reason': str(error)})
                continue
            raise AssertionError('unsupported input was accepted')
        document, stats = adapter(native, case['url'], document_id=case['id'], revision=case['sha256'])
        validate_document(document, block_schemas=extension_registry())
        verify_retention(native, document, case['provider'])
        assert stats['mapped_items'] == stats['source_items']
        blocks = document['structure']['text']['blocks']
        result = {'id': case['id'], 'source': source, 'status': 'mapped_and_validated', **stats,
                  'normalized_types': dict(Counter(b['type'] for b in blocks)),
                  'native_json_reconstruction_equal': True,
                  'normalized_text_chars': len(document['fields']['text']),
                  'text_spans_valid': True,
                  'uses_only_core_block_types': stats['extension_blocks'] == 0,
                  'vendor_specific_table_payloads': sum(b['type'] == 'table' for b in blocks),
                  'binary_assets_verified': False}
        excerpt_path = here / 'docling_report_excerpt.json'
        if case['id'] == 'docling-multi_page' and excerpt_path.exists():
            excerpt = json.loads(excerpt_path.read_text())
            validate_document(excerpt)
            assert excerpt['source_revision'] == document['source_revision']
            expected = deepcopy(document['structure']['text']['blocks'][:2])
            for block in expected:
                block.pop('extensions', None)
                for location in block['locations']:
                    location.pop('bbox', None)
                    location.pop('source_ref', None)
            assert excerpt['structure']['text']['blocks'] == expected
            assert excerpt['fields']['text'] == document['fields']['text'][:expected[-1]['end']]
            assert excerpt['metadata']['_rag']['preview'] is True
            result['report_excerpt_matches_official_mapping'] = True
        if output_dir:
            (output_dir / (case['id'] + '.text-spans.json')).write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
        try:
            page_document = as_page_blocks(document)
        except ValueError as error:
            result['page_blocks'] = {'status': 'not_losslessly_convertible_by_reference_adapter', 'reason': str(error)}
        else:
            validate_document(page_document, block_schemas=extension_registry())
            verify_retention(native, page_document, case['provider'])
            result['page_blocks'] = {'status': 'mapped_and_validated'}
            if output_dir:
                (output_dir / (case['id'] + '.page-blocks.json')).write_text(json.dumps(page_document, ensure_ascii=False, indent=2) + '\n')
        results.append(result)
    return {
        'contract': 'parsed-document/0.1-draft', 'date': '2026-10-30',
        'scope': 'Pinned official output JSON mapping and conformance only; no parser model, OCR, binary download, Chunker, retrieval or production SDK executed.',
        'counts': {'cases': len(results), 'positive': sum(r['status'] == 'mapped_and_validated' for r in results),
                   'negative': sum(r['status'] == 'rejected_as_expected' for r in results)},
        'results': results,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.cache_dir, args.output_dir)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'counts': report['counts'], 'report': str(args.report)}, ensure_ascii=False))
