"""Validate and render report examples into docs 13/14 from canonical JSON.

Requires examples/parsed_document/requirements.txt. This only updates marked
example blocks; it does not execute an API, Parser, Chunker, or resource fetch.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'examples/parsed_document'))
from validate import validate_document


def readable_json(value, depth=0):
    """Keep small objects compact so all top-level keys remain visible."""
    compact = json.dumps(value, ensure_ascii=False)
    if depth and len(compact) + 2 * depth <= 108:
        return compact
    indent = '  ' * depth
    child_indent = '  ' * (depth + 1)
    if isinstance(value, dict):
        lines = [child_indent + json.dumps(k, ensure_ascii=False) + ': ' + readable_json(v, depth+1)
                 for k, v in value.items()]
        return '{\n' + ',\n'.join(lines) + '\n' + indent + '}'
    if isinstance(value, list):
        return '[\n' + ',\n'.join(child_indent + readable_json(v, depth+1) for v in value) + '\n' + indent + ']'
    return compact


def example(heading, explanation, value):
    return heading + '\n\n' + explanation + '\n\n```json\n' + readable_json(value) + '\n```\n'


def replace_section(path, kind, text):
    content = path.read_text()
    start = f'<!-- classification-examples:{kind}:start -->'
    end = f'<!-- classification-examples:{kind}:end -->'
    replacement = start + '\n\n' + text.rstrip() + '\n\n' + end + '\n\n'
    if start in content:
        content = re.sub(re.escape(start) + r'.*?' + re.escape(end) + r'\n*', lambda _: replacement, content, count=1, flags=re.S)
    else:
        marker = '### 0.3 '
        index = content.index(marker)
        content = content[:index] + replacement + content[index:]
    path.write_text(content)


def main():
    catalog = json.loads((Path(__file__).parent / 'report_cases.json').read_text())
    source_dir = ROOT / 'examples/parsed_document'
    parsed_examples = [json.loads((source_dir / (name + '.json')).read_text()) for name in
                       ('plain_text', 'units', 'table_rows', 'image_description', 'docling_report_excerpt')]
    for document in parsed_examples:
        validate_document(document)
    ingestion = deepcopy(catalog['ingestion'])
    schema = json.loads((ROOT / 'schemas/ingestion_document.schema.json').read_text())
    for value in ingestion.values():
        Draft202012Validator(schema).validate(value)
    import base64
    assert base64.b64decode(ingestion['base64']['base64'], validate=True).decode('utf-8') == catalog['base64_decoded_text']
    reconstructed = {**ingestion['preparsed']['content'],
                     'document_id': ingestion['preparsed']['document_id'],
                     'source_revision': ingestion['preparsed']['source_revision'],
                     'metadata': ingestion['preparsed']['metadata']}
    validate_document(reconstructed)
    assert reconstructed == parsed_examples[1]

    text13 = '以下是符合目前 IngestionDocument 外層 Schema 的單筆例子，與 Parser Input 使用同一份契約。例子由 [共用資料來源及產生工具](../examples/contracts/render_classification_examples.py) 驗證／產生，資料見 [report_cases.json](../examples/contracts/report_cases.json)；此處驗證資料形狀，尚未執行 API。\n\n'
    for heading, description, key in [
        ('#### 0.2.1 content：直接傳文字', '只有文件 ID 與內容即可表達最簡單情境；相容 Parser 產生 ParsedDocument。', 'text'),
        ('#### 0.2.2 content：直接傳多欄位 JSON', '這是一筆文件的原文、標題與既有摘要；metadata 另外保存部門。CSV 映射後也可形成這種單筆資料。', 'record'),
        ('#### 0.2.3 base64：傳送編碼後的檔案內容', '用短文字檔示範 Base64，實際可解碼為「清潔前先斷電。」。PDF／PPTX／Excel 使用相同傳輸欄位，須填入完整檔案內容、正確 media_type 並有相容 Parser。', 'base64'),
        ('#### 0.2.4 uri：取得 URL 指向的檔案', '只傳資源位置，由共用能力取得 PDF，再交給相容 Parser；這個示意網址未進行下載／連線驗證。', 'uri'),
        ('#### 0.2.5 content：上游已整理好的 Units', 'content.units 是平面的內容單位列表，由相容 Adapter 驗證後與外層 ID／版本／metadata 組成 ParsedDocument。schema_id 是需註冊的示意識別；不是任何 Parser 都自動支援。', 'preparsed'),
    ]:
        text13 += example(heading, description, ingestion[key]) + '\n'
    text13 += '上述五例都符合共同外層；media_type／schema_id 能省略的條件仍依正文。對應的 Parser／服務能力必須另外具備，範例通過 Schema 不代表 Runtime 已實作。'

    text14 = '所有例子共用四個頂層鍵；分類代表來源情境，不是不同結構型別。\n\n'
    labels = ['純文字／紀錄：一個 Unit', '多頁／章節：獨立 Units，保留 Markdown 標題',
              '表格：逐列補齊語意', '圖片：描述文字與來源 URI', '既有 Docling 官方文字摘錄：重新包裝成一個 Unit']
    for i, (label, value) in enumerate(zip(labels, parsed_examples), 1):
        text14 += example(f'#### 0.1.{i} {label}', '資料形狀範例；不代表已執行正式 Parser 或 Chunker。', value) + '\n'
    replace_section(ROOT / 'docs/13_ingestion_parser_input_contract.md', 'ingestion', text13)
    replace_section(ROOT / 'docs/14_parsed_document_contract.md', 'parsed', text14)
    print(json.dumps({'ingestion_examples': len(ingestion), 'parsed_examples': len(parsed_examples),
                      'preparsed_reconstruction': True}))



if __name__ == '__main__':
    main()
