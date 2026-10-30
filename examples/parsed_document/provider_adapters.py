"""Reference mappings for pinned official fixtures, not production parsers.

No PDF/OCR/model execution, URI fetching, or implicit fallback happens here.
Vendor payload preservation is distinct from portable semantic normalization.
"""
from __future__ import annotations

from copy import deepcopy
from validate import TEXT_SPANS, PAGE_BLOCKS


def extension_registry() -> dict:
    # Explicitly registered opaque vendor items: retaining these does not make a
    # generic chunker understand formulas, group semantics, or binary assets.
    return {
        'source.docling-item/1.10.0': {
            'type': 'object', 'required': ['self_ref', 'label'],
            'properties': {'self_ref': {'type': 'string'}, 'label': {'type': 'string'}},
        }
    }


def _document(document_id, revision, source, blocks, fields, pages, native):
    """Build a text-spans document with stable synthetic normalization offsets."""
    parts = []
    cursor = 0
    for block in blocks:
        text = block.pop('_text', '')
        if text:
            if parts:
                cursor += 2
            block['start'] = cursor
            block['end'] = cursor + len(text)
            cursor += len(text)
            parts.append(text)
    fields['text'] = '\n\n'.join(parts)
    structure = {'schema_id': TEXT_SPANS, 'blocks': blocks,
                 'extensions': {'source.page_numbers': list(pages)}}
    return {
        'document_id': document_id,
        'source_revision': revision,
        'fields': fields,
        'metadata': {'_rag': {'fixture_source': source, 'native_document': native}},
        'structure': {'text': structure},
    }


def from_docling(native: dict, source: str, document_id='docling-fixture', revision='fixture'):
    if native.get('schema_name') != 'DoclingDocument' or native.get('version') != '1.10.0':
        raise ValueError('reference adapter only covers pinned DoclingDocument 1.10.0 fixtures')
    fields, blocks, seen = {}, [], set()
    collections = ('texts', 'tables', 'pictures', 'groups', 'key_value_items', 'form_items', 'field_regions', 'field_items')
    nodes = {item['self_ref']: item for name in collections for item in native.get(name, [])}
    id_map = {pointer: f'b{i:04d}' for i, pointer in enumerate(nodes)}
    mimetype = native.get('origin', {}).get('mimetype', '')
    if 'spreadsheet' in mimetype:
        location_kind = 'sheet'
    elif 'presentation' in mimetype:
        location_kind = 'slide'
    else:
        location_kind = 'page'

    def sheet_name(item):
        visited = set()
        while item:
            if item.get('label') == 'sheet':
                return item.get('name', item['self_ref'])
            pointer = item.get('parent', {}).get('$ref')
            if pointer in visited:
                raise ValueError('cyclic native parent')
            visited.add(pointer)
            item = nodes.get(pointer)
        return None

    def locations(item):
        out = []
        for prov in item.get('prov', []):
            location = {'kind': location_kind, 'source_ref': item['self_ref']}
            page_no = prov['page_no']
            if location_kind == 'sheet':
                name = sheet_name(item)
                if not name:
                    raise ValueError('sheet source without sheet identity')
                location['sheet_name'] = name
                # XLSX coordinates are native grid-like values, not PDF points.
                # Original prov, including its bbox, remains in extensions.
            else:
                location['slide_number' if location_kind == 'slide' else 'page_number'] = page_no
                box = prov.get('bbox')
                if box:
                    size = native.get('pages', {}).get(str(page_no), {}).get('size', {})
                    origin = {'TOPLEFT': 'top-left', 'BOTTOMLEFT': 'bottom-left'}[box['coord_origin']]
                    unit = 'emu' if location_kind == 'slide' else ('pt' if mimetype == 'application/pdf' else 'source')
                    location['bbox'] = {'left': box['l'], 'top': box['t'], 'right': box['r'],
                                        'bottom': box['b'], 'origin': origin, 'unit': unit,
                                        **{k: size[k] for k in ('width', 'height') if k in size}}
            out.append(location)
        if not out:
            out = [{'kind': 'element', 'element_ref': item['self_ref']}]
        return out

    def visit(pointer):
        if pointer in seen:
            return
        if pointer in ('#/body', '#/furniture'):
            seen.add(pointer)
            for child in native[pointer[2:]].get('children', []):
                visit(child['$ref'])
            return
        if pointer not in nodes:
            raise ValueError(f'unresolved native reference: {pointer}')
        seen.add(pointer)
        item = nodes[pointer]
        label = item['label']
        types = {'title': 'heading', 'section_header': 'heading', 'text': 'paragraph',
                 'paragraph': 'paragraph', 'list_item': 'list_item', 'code': 'code',
                 'caption': 'paragraph', 'page_header': 'paragraph', 'page_footer': 'paragraph',
                 'table': 'table', 'picture': 'image'}
        kind = types.get(label, 'extension')
        block = {'block_id': id_map[pointer], 'type': kind, 'locations': locations(item),
                 'extensions': {'source.docling': deepcopy(item)}}
        if pointer.startswith('#/groups/'):
            kind = block['type'] = 'extension'
        parent = item.get('parent', {}).get('$ref')
        if parent in id_map:
            block['parent_id'] = id_map[parent]
        if kind == 'heading' and isinstance(item.get('level'), int) and item['level'] > 0:
            block['level'] = item['level']
        roles = {'caption': 'caption', 'page_header': 'header', 'page_footer': 'footer'}
        if label in roles:
            block['role'] = roles[label]
        text = item.get('text', '')
        if kind == 'table':
            data = deepcopy(item.get('data', {}))
            data_key = f'table_{len(fields)}'
            fields[data_key] = {'schema_id': 'source.docling-table/1.10.0', 'payload': data}
            block['data_ref'] = data_key
            cells = sorted(data.get('table_cells', []), key=lambda c: (c['start_row_offset_idx'], c['start_col_offset_idx']))
            text = '\n'.join(cell.get('text', '') for cell in cells if cell.get('text'))
        elif kind == 'image':
            data_key = f'image_{len(fields)}'
            image = item.get('image')
            fields[data_key] = {'status': 'referenced' if image else 'unavailable',
                                'source_ref': pointer, **({'native_image': deepcopy(image)} if image else {})}
            block['data_ref'] = data_key
        elif kind == 'extension':
            data_key = f'native_{len(fields)}'
            fields[data_key] = deepcopy(item)
            block['data_ref'] = data_key
            block['extension_type'] = 'source.docling-item/1.10.0'
        if kind in ('heading', 'paragraph', 'list_item', 'code') and not text:
            raise ValueError('empty text item requires an explicit policy, not silent dropping')
        block['_text'] = text
        blocks.append(block)
        for child in item.get('children', []):
            visit(child['$ref'])

    visit('#/body')
    if 'furniture' in native:
        visit('#/furniture')
    # Retain nodes not linked by a root instead of silently losing them.
    for pointer in nodes:
        visit(pointer)
    retained = {k: deepcopy(v) for k, v in native.items() if k not in collections}
    doc = _document(document_id, revision, source, blocks, fields, sorted(int(k) for k in native.get('pages', {})), retained)
    return doc, {'source_items': len(nodes), 'mapped_items': len(blocks),
                 'extension_blocks': sum(b['type'] == 'extension' for b in blocks),
                 'missing_image_assets': sum(v.get('status') == 'unavailable' for v in fields.values() if isinstance(v, dict)),
                 'location_kind': location_kind}


def _inline_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for span in content:
            if span.get('type') not in ('text', 'equation_inline') or not isinstance(span.get('content'), str):
                raise ValueError('unsupported inline object; do not flatten blindly')
            parts.append(span['content'])
        return ''.join(parts)
    raise ValueError('unsupported content representation')


def from_mineru(native: dict, source: str, document_id='mineru-fixture', revision='fixture'):
    if native.get('schema') != 'docvortex.middle' or native.get('schema_version') != '2.0':
        raise ValueError('reference adapter only covers MiddleJson docvortex.middle/2.0; not ModelJson or CLI envelopes')
    blocks = []
    pages = native['pages']
    for page in pages:
        for number, item in enumerate(page['blocks']):
            kind = item['type']
            types = {'text': 'paragraph', 'paragraph_title': 'heading', 'doc_title': 'heading',
                     'header': 'paragraph', 'footer': 'paragraph', 'aside_text': 'paragraph', 'page_footnote': 'paragraph'}
            if kind not in types:
                raise ValueError(f'unsupported MinerU block in reference adapter: {kind}')
            text = _inline_text(item['content'])
            if not text:
                raise ValueError('empty text block')
            location = {'kind': 'page', 'page_number': page['page_idx'] + 1,
                        'source_ref': f'pages/{page["page_idx"]}/blocks/{number}'}
            if 'bbox' in item:
                left, top, right, bottom = item['bbox']
                location['bbox'] = {'left': left, 'top': top, 'right': right, 'bottom': bottom,
                                    'origin': 'top-left', 'unit': 'source'}
            block = {'block_id': f'p{page["page_idx"]}_b{number}', 'type': types[kind], '_text': text,
                     'locations': [location], 'extensions': {'source.mineru': deepcopy(item)}}
            if block['type'] == 'heading' and item.get('level', 0) > 0:
                block['level'] = item['level']
            if kind in ('header', 'footer', 'aside_text', 'page_footnote'):
                block['role'] = {'aside_text': 'aside', 'page_footnote': 'note'}.get(kind, kind)
            if item.get('continues_prev'):
                candidates = [b for b in blocks if b['type'] == block['type'] and b.get('role', 'body') == block.get('role', 'body')]
                if not candidates:
                    raise ValueError('unresolvable native continuation')
                block['continuation_of'] = candidates[-1]['block_id']
            blocks.append(block)
    retained = {k: deepcopy(v) for k, v in native.items() if k != 'pages'}
    doc = _document(document_id, revision, source, blocks, {}, [p['page_idx']+1 for p in pages], retained)
    doc['metadata']['_rag']['native_pages'] = [{k: deepcopy(v) for k, v in p.items() if k != 'blocks'} for p in pages]
    return doc, {'source_items': sum(len(p['blocks']) for p in pages), 'mapped_items': len(blocks),
                 'extension_blocks': 0, 'missing_image_assets': 0, 'location_kind': 'page'}


def as_page_blocks(document: dict) -> dict:
    """Convert only if source page grouping preserves original block order.

    No guessed page assignment for groups or cross-page elements: reject those
    cases instead. Such documents remain valid text-spans inputs.
    """
    out = deepcopy(document)
    structure = out['structure']['text']
    numbers = structure['extensions']['source.page_numbers']
    grouped = {n: [] for n in numbers}
    previous_page = -1
    for block in structure['blocks']:
        locations = block.get('locations', [])
        page_numbers = {l.get('page_number') for l in locations if l['kind'] == 'page'}
        if len(page_numbers) != 1:
            raise ValueError('cannot losslessly infer a unique page for each block')
        page_number = page_numbers.pop()
        if page_number < previous_page:
            raise ValueError('page grouping would reorder reading order')
        previous_page = page_number
        start, end = block.pop('start', None), block.pop('end', None)
        if start is not None:
            block['text'] = out['fields']['text'][start:end]
        grouped[page_number].append(block)
    out['structure']['text'] = {'schema_id': PAGE_BLOCKS, 'pages': [
        {'page_number': n, 'blocks': grouped[n]} for n in numbers
    ]}
    return out
