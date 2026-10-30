"""Render the short report views from canonical Chunk cases."""
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def compact_json(value):
    return '```json\n' + json.dumps(value, ensure_ascii=False, indent=2) + '\n```'


def main():
    cases = {case['case_id']: case for case in json.loads((HERE / 'cases.json').read_text())}
    plain = cases['default_text']['chunks'][0]
    multi = cases['two_plus_three']['chunks']
    content = '\n\n'.join([
        '### 0.2 使用同一份 Schema 的資料例子',
        '以下由共用 cases.json 產生，包含完整預設 Chunk、進階多欄位結果及來源／向量片段。Hash 是參考規則的實際結果；完整來源與設定見同一案例檔。',
        '**預設：只切 text，不複製其他 fields**', compact_json(plain),
        '**進階：T 切 2 段、F 切 3 段，明確設定互相複製完整欄位**',
        '| ordinal | task_id | fields.text | fields.faq |\n|---|---|---|---|\n' + '\n'.join(
            f"| {c['metadata']['_rag']['chunking']['chunk_ordinal']} | {c['metadata']['_rag']['chunking']['task_id']} | {c['fields']['text']} | {c['fields']['faq']} |" for c in multi),
        '**結構來源：從兩頁 Block 組成同一 Chunk，保留兩筆來源與各自輸出位置**',
        '以下是 page_blocks 案例的 metadata._rag.source_refs；頁面不是預設強制切分邊界。',
        compact_json(cases['page_blocks']['chunks'][0]['metadata']['_rag']['source_refs']),
        '**Embedding 後：vectors.text 的內容**',
        '以下向量為契約用示意數值，沒有呼叫模型；Profile 與來源欄位必須符合可信 Binding。',
        compact_json(cases['embedded']['chunks'][0]['vectors']['text']),
    ])
    p = ROOT / 'docs/15_chunk_contract.md'
    text = p.read_text()
    start = '<!-- chunk-report-examples:start -->'
    end = '<!-- chunk-report-examples:end -->'
    before, rest = text.split(start)
    _, after = rest.split(end)
    p.write_text(before + start + '\n\n' + content + '\n\n' + end + after)
    print('rendered docs/15_chunk_contract.md from 7 canonical cases')


if __name__ == '__main__':
    main()
