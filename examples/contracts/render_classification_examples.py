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
    """Keep small objects compact so all five top-level keys remain visible."""
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
    plain = json.loads((source_dir / 'plain_text.json').read_text())
    spans = json.loads((source_dir / 'text_spans.json').read_text())
    pages = json.loads((source_dir / 'page_blocks.json').read_text())
    # Report views omit optional detail; complete source examples stay canonical.
    spans['structure']['text'].pop('pages', None)
    spans['structure']['text'].pop('split_points', None)
    for block in spans['structure']['text']['blocks']:
        block.pop('locations', None)
    pages['structure']['text'].pop('split_points', None)
    custom = deepcopy(plain)
    custom['structure'] = {'text': catalog['custom_structure']}
    structure_schemas = catalog['structure_schemas']
    parsed_examples = [plain, spans, pages, custom]
    for document in parsed_examples:
        validate_document(document, structure_schemas=structure_schemas)
    # A custom ID is illustrative, not a builtin or a bypass for registration.
    try:
        validate_document(custom)
    except ValueError:
        custom_rejected_without_registration = True
    else:
        raise AssertionError('custom structure unexpectedly accepted without registration')

    ingestion = deepcopy(catalog['ingestion'])
    ingestion['preparsed'] = {
        'document_id': spans['document_id'],
        'source_revision': spans['source_revision'],
        'schema_id': 'example.preparsed-content/0.1-draft',
        'content': {'fields': spans['fields'], 'structure': spans['structure']},
        'metadata': spans['metadata'],
    }
    schema = json.loads((ROOT / 'schemas/ingestion_document.schema.json').read_text())
    validator = Draft202012Validator(schema)
    for value in ingestion.values():
        validator.validate(value)
    # The example base64 encodes a real short UTF-8 text file, not a fake PDF.
    import base64
    assert base64.b64decode(ingestion['base64']['base64'], validate=True).decode('utf-8') == catalog['base64_decoded_text']
    reconstructed = {**ingestion['preparsed']['content'],
                     'document_id': ingestion['preparsed']['document_id'],
                     'source_revision': ingestion['preparsed']['source_revision'],
                     'metadata': ingestion['preparsed']['metadata']}
    assert reconstructed == spans
    validate_document(reconstructed)

    text13 = '以下是符合目前 IngestionDocument 外層 Schema 的單筆例子，與 Parser Input 使用同一份契約。例子由 [共用資料來源及產生工具](../examples/contracts/render_classification_examples.py) 驗證／產生，資料見 [report_cases.json](../examples/contracts/report_cases.json)；此處驗證資料形狀，尚未執行 API。\n\n'
    for heading, description, key in [
        ('#### 0.2.1 content：直接傳文字', '只有文件 ID 與內容即可表達最簡單情境；相容 Parser 產生 ParsedDocument。', 'text'),
        ('#### 0.2.2 content：直接傳多欄位 JSON', '這是一筆文件的原文、標題與既有摘要；metadata 另外保存部門。CSV 映射後也可形成這種單筆資料。', 'record'),
        ('#### 0.2.3 base64：傳送編碼後的檔案內容', '用短文字檔示範 Base64，實際可解碼為「清潔前先斷電。」。PDF／PPTX／Excel 使用相同傳輸欄位，須填入完整檔案內容、正確 media_type 並有相容 Parser。', 'base64'),
        ('#### 0.2.4 uri：取得 URL 指向的檔案', '只傳資源位置，由共用能力取得 PDF，再交給相容 Parser；這個示意網址未進行下載／連線驗證。', 'uri'),
        ('#### 0.2.5 content：上游已經解析並保留結構', '原文與 heading／paragraph 範圍已整理好，由相容 Adapter 驗證與組成 ParsedDocument。外層 schema_id 是「輸入內容形狀」的示意識別，須註冊對應 Adapter；內層 schema_id 是文字結構規格。API body 使用 IngestionDocument，Adapter 以 content 中的 fields／structure 組成 ParsedDocument。', 'preparsed'),
    ]:
        text13 += example(heading, description, ingestion[key]) + '\n'
    text13 += '上述五例都符合共同外層；media_type／schema_id 能省略的條件仍依正文。對應的 Parser／服務能力必須另外具備，範例通過 Schema 不代表 Runtime 已實作。'

    text14 = '以下先列四種分類，再附一份從 Docling 官方輸出映射而來的精簡例子；都使用 ParsedDocument 的五個頂層 key。它們是 Parser 的輸出／Chunker 的輸入，與 13 的 IngestionDocument 分屬不同階段。前三種分類由 §1 的共用 JSON 範例產生報告用精簡視圖，只省略可選資訊；自訂例子的資料與示意註冊 Schema 見 [report_cases.json](../examples/contracts/report_cases.json)。\n\n'
    for heading, description, value in [
        ('#### 0.2.1 無額外結構：只有可處理的文字欄位', '原文與標題在 fields，structure 為空；一般文字 Chunker 可以依 Token 或分隔規則處理選定文字欄位。', plain),
        ('#### 0.2.2 text-spans：全文加上標題／段落範圍', 'fields.text 是基準；[0,4) 是標題、[5,12) 是段落，Block 不重複保存文字。完整範例另有頁碼與切分點，此處省略可選資訊。', spans),
        ('#### 0.2.3 page-blocks：按頁保存 Block 物件', 'Block.text 是基準；例子有兩頁。fields.text 是以兩個換行串接的衍生值，Chunker 仍可依設定跨頁合併，頁面不是強制切分邊界。', pages),
        ('#### 0.2.4 已註冊自訂結構：企業自己的章節分類', 'company.custom/1 是示意客製規格，payload 記錄企業的章節分類；產生／驗證本例時，工具明確註冊了要求 section 為字串的 Schema。未註冊時會拒絕，且需要相容 Component，不表示平台預設支援此名稱。', custom),
    ]:
        text14 += example(heading, description, value) + '\n'
    provider_excerpt = json.loads((source_dir / 'docling_report_excerpt.json').read_text())
    validate_document(provider_excerpt)
    text14 += example('#### 0.2.5 Docling 實際映射：標題、段落與來源頁碼',
        '這是官方 multi_page 測資經既有參考 Adapter 轉換後，取前兩個 Block 的報告視圖；來源與雜湊見 §5。全文取至第二個 Block 結尾，省略其他內容、bbox 與原生擴充，metadata 明示為摘錄。這是轉成既有 text-spans 的例子，沒有建立自訂結構。Docling 第二個元素的局部 charspan 原為 [0,117)，重組全文後對應 [37,154)，因此不能把原生局部位置直接照搬。完整可驗證 JSON 見 [docling_report_excerpt.json](../examples/parsed_document/docling_report_excerpt.json)。',
        provider_excerpt) + '\n'
    text14 += '四種表示的共同外層不變，差異集中在 structure 與內容基準；本輪未更改 Schema，也未新增 Parser／Chunker 執行能力。'
    replace_section(ROOT / 'docs/13_ingestion_parser_input_contract.md', 'ingestion', text13)
    replace_section(ROOT / 'docs/14_parsed_document_contract.md', 'parsed', text14)
    report = {'ingestion_examples': len(ingestion), 'parsed_document_examples': len(parsed_examples) + 1,
              'custom_rejected_without_registration': custom_rejected_without_registration,
              'preparsed_input_reconstructs_valid_output': True,
              'base64_example_decodes_to_declared_text': True}
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
