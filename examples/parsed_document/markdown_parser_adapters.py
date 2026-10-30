"""Conformance reference adapters for Markdown-focused parser outputs.

These are examples, not production components. JSON Schema remains unchanged.
Markdown offsets refer to the exact emitted Markdown, not source PDF glyphs.
"""
from copy import deepcopy
import re

from markdown_it import MarkdownIt
from validate import TEXT_SPANS, PAGE_BLOCKS, rendered_page_text


def _base(document_id, revision, native, provider):
    return {
        'document_id': document_id, 'source_revision': revision,
        'fields': {}, 'metadata': {'_rag': {'provider': provider, 'native_result': deepcopy(native),
                                         'field_formats': {'text': 'text/markdown'}}},
        'structure': {},
    }


def _markdown_blocks(text, fields, prefix):
    # Markdown-it's maps count LF-delimited lines; str.splitlines() also splits
    # form-feed and would corrupt offsets for MarkItDown PDF output.
    starts = [0] + [m.end() for m in re.finditer('\n', text)]
    tokens = MarkdownIt('commonmark').enable('table').parse(text)
    kinds = {'heading_open': 'heading', 'paragraph_open': 'paragraph',
             'list_item_open': 'list_item', 'fence': 'code', 'code_block': 'code',
             'table_open': 'table'}
    blocks, covered_end = [], -1
    headings = []
    for token in tokens:
        if token.type not in kinds or token.map is None:
            continue
        start = starts[token.map[0]]
        end = starts[token.map[1]] if token.map[1] < len(starts) else len(text)
        if start < covered_end:
            continue  # nested paragraph is included by its list item/table
        if start == end:
            continue
        block = {'block_id': f'{prefix}_{len(blocks)}', 'type': kinds[token.type],
                 'start': start, 'end': end}
        if block['type'] == 'heading':
            level = int(token.tag[1:])
            while headings and headings[-1][0] >= level:
                headings.pop()
            if headings:
                block['parent_id'] = headings[-1][1]
            block['level'] = level
            headings.append((level, block['block_id']))
        elif headings:
            block['parent_id'] = headings[-1][1]
        if block['type'] == 'table':
            key = f'table_{block["block_id"]}'
            fields[key] = {'format': 'markdown', 'text': text[start:end]}
            block['data_ref'] = key
        blocks.append(block)
        covered_end = end
    return blocks


def from_markdown(markdown, *, document_id, revision, native, provider, structured=True, title=None):
    if not isinstance(markdown, str):
        raise ValueError('expected emitted Markdown string')
    doc = _base(document_id, revision, native, provider)
    doc['fields']['text'] = markdown
    if title:
        doc['fields']['title'] = title
    if structured:
        doc['structure']['text'] = {'schema_id': TEXT_SPANS,
                                    'blocks': _markdown_blocks(markdown, doc['fields'], 'b')}
    return doc


def _page_number(chunk):
    metadata = chunk['metadata']
    # Tested 2.0 modes differ: legacy uses page, Layout uses page_number.
    values = [metadata[k] for k in ('page', 'page_number') if k in metadata]
    if not values or len(set(values)) != 1 or not isinstance(values[0], int) or values[0] < 1:
        raise ValueError('missing or conflicting producer page identity')
    return values[0]


def from_page_chunks(chunks, *, document_id, revision, provider, profile=PAGE_BLOCKS):
    if not isinstance(chunks, list) or not chunks:
        raise ValueError('expected nonempty list of producer page chunks')
    doc = _base(document_id, revision, chunks, provider)
    pages, spans, span_pages, raw_texts = [], [], [], []
    cursor = 0
    for index, chunk in enumerate(chunks):
        page_number = _page_number(chunk)
        text = chunk['text']
        if not isinstance(text, str):
            raise ValueError('page text must be a string')
        if index:
            cursor += 2
        blocks = _markdown_blocks(text, doc['fields'], f'p{page_number}')
        page_blocks = []
        for block in blocks:
            start, end = block['start'], block['end']
            locations = []
            for box in chunk.get('page_boxes', []):
                if not isinstance(box.get('pos'), (list, tuple)) or len(box['pos']) != 2:
                    continue
                a, b = box['pos']
                if not (0 <= a <= b <= len(text)):
                    raise ValueError('native page-box pos outside emitted Markdown')
                if max(start, a) < min(end, b):
                    x0, y0, x1, y1 = box['bbox']
                    locations.append({'kind': 'page', 'page_number': page_number,
                                      'source_ref': f'page/{page_number}/box/{box["index"]}',
                                      'bbox': {'left': x0, 'top': y0, 'right': x1, 'bottom': y1,
                                               'origin': 'top-left', 'unit': 'pt'}})
            if not locations:
                locations = [{'kind': 'page', 'page_number': page_number}]
            block['locations'] = locations
            page_block = {k: deepcopy(v) for k, v in block.items() if k not in ('start', 'end')}
            page_block['text'] = text[start:end]
            page_blocks.append(page_block)
            span = deepcopy(block)
            span['start'] += cursor
            span['end'] += cursor
            spans.append(span)
        pages.append({'page_number': page_number, 'blocks': page_blocks})
        span_pages.append({'page_number': page_number, 'start': cursor, 'end': cursor + len(text)})
        raw_texts.append(text)
        cursor += len(text)
    if profile == PAGE_BLOCKS:
        structure = {'schema_id': PAGE_BLOCKS, 'pages': pages}
        doc['structure']['text'] = structure
        doc['fields']['text'] = rendered_page_text(structure)
    elif profile == TEXT_SPANS:
        doc['fields']['text'] = '\n\n'.join(raw_texts)
        doc['structure']['text'] = {'schema_id': TEXT_SPANS, 'blocks': spans, 'pages': span_pages}
    else:
        raise ValueError('unsupported target profile')
    return doc


def from_layout_json(native, *, document_id, revision, profile=TEXT_SPANS):
    if not isinstance(native, dict) or not isinstance(native.get('pages'), list):
        raise ValueError('expected PyMuPDF Layout JSON document')
    doc = _base(document_id, revision, native, 'pymupdf-layout-json')
    doc['metadata']['_rag']['field_formats']['text'] = 'text/plain'
    pages, blocks, parts, ranges = [], [], [], []
    cursor = 0
    classes = {'title': 'heading', 'section-header': 'heading', 'text': 'paragraph',
               'list-item': 'list_item', 'caption': 'paragraph', 'page-header': 'paragraph',
               'page-footer': 'paragraph', 'footnote': 'paragraph', 'table': 'table'}
    roles = {'caption': 'caption', 'page-header': 'header', 'page-footer': 'footer', 'footnote': 'note'}
    for page in native['pages']:
        page_number, page_blocks = page['page_number'], []
        page_start = cursor
        for index, box in enumerate(page['boxes']):
            label = box['boxclass']
            if label not in classes:
                raise ValueError(f'unsupported Layout JSON class in reference adapter: {label}')
            if label == 'table':
                text = box['table']['markdown']
            else:
                text = '\n'.join(''.join(s['text'] for s in line['spans']) for line in box.get('textlines') or [])
            if not text:
                raise ValueError('empty box text requires a separate policy')
            if parts:
                cursor += 2
            start = cursor
            cursor += len(text)
            parts.append(text)
            block = {'block_id': f'p{page_number}_box{index}', 'type': classes[label],
                     'start': start, 'end': cursor,
                     'locations': [{'kind': 'page', 'page_number': page_number,
                                    'source_ref': f'pages/{page_number}/boxes/{index}',
                                    'bbox': {'left': box['x0'], 'top': box['y0'], 'right': box['x1'], 'bottom': box['y1'],
                                             'origin': 'top-left', 'unit': 'pt',
                                             'width': page['width'], 'height': page['height']}}],
                     'extensions': {'source.pymupdf': deepcopy(box)}}
            if block['type'] == 'heading' and box.get('header_level', 0) > 0:
                block['level'] = box['header_level']
            if label in roles:
                block['role'] = roles[label]
            if label == 'table':
                key = f'table_p{page_number}_{index}'
                doc['fields'][key] = {'schema_id': 'source.pymupdf-table/2.0', 'payload': deepcopy(box['table'])}
                block['data_ref'] = key
            blocks.append(block)
            page_blocks.append({**{k: deepcopy(v) for k, v in block.items() if k not in ('start', 'end')}, 'text': text})
        pages.append({'page_number': page_number, 'blocks': page_blocks})
        ranges.append({'page_number': page_number, 'start': page_start, 'end': cursor})
    if profile == TEXT_SPANS:
        doc['fields']['text'] = '\n\n'.join(parts)
        doc['structure']['text'] = {'schema_id': TEXT_SPANS, 'blocks': blocks, 'pages': ranges}
    elif profile == PAGE_BLOCKS:
        doc['structure']['text'] = {'schema_id': PAGE_BLOCKS, 'pages': pages}
        doc['fields']['text'] = rendered_page_text(doc['structure']['text'])
    else:
        raise ValueError('unsupported target profile')
    return doc
