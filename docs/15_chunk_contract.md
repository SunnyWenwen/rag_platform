# 15 — Chunk Contract

更新：2026-11-02。Chunk **0.2-draft** 保持六個頂層鍵；來源追溯改用 ParsedDocument.units 的位置。舊 0.1 SourceRef 不默默相容。

## 0. 情境與結果摘要

| 情境 | 行為 |
|---|---|
| 預設 | 每個 Unit 的 text 獨立切分，輸出 Chunk.fields.text；copy_fields=[] |
| 多 Unit | 各筆結果串接，2＋3＝5；不合併、不跨 Unit overlap |
| 多欄位任務 | 每個任務遍歷 Units，結果相加，不做笛卡兒積 |
| 保留原文／上下文 | copy 同一 Unit 的欄位；原文另名 original_text，不能覆蓋切片 |
| 來源位置 | metadata._rag.source_refs：unit_index＋field＋start/end |
| Embedding／Indexing | 沿用命名向量物件與完整保存規則 |

<!-- chunk-report-examples:start -->

### 0.2 使用同一份 Schema 的資料例子

以下由共用 cases.json 產生，包含完整預設 Chunk、進階多欄位結果及來源／向量片段。Hash 是參考規則的實際結果；完整來源與設定見同一案例檔。

**預設：只切 text，不複製其他 fields**

```json
{
  "chunk_id": "chk_25f40b1f36ef7154df4806eb5fe1317db1836f46e0705749efd676b44cbe9182",
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {
    "text": "清潔前先斷電。"
  },
  "metadata": {
    "department": "engineering",
    "_rag": {
      "source_refs": [
        {
          "unit_index": 0,
          "field": "text",
          "output_field": "text",
          "role": "split",
          "start": 5,
          "end": 12
        }
      ],
      "chunking": {
        "chunking_fingerprint": "40da9219f54a8d552281e6fa3573e98352e450df39d8ac6e6c3ed287877a31a3",
        "chunk_ordinal": 0,
        "task_id": "text"
      }
    }
  },
  "vectors": {}
}
```

**進階：T 切 2 段、F 切 3 段，各自預設輸出 text；完整來源明確複製到不同名稱**

| ordinal | task_id | fields.text（片段） | fields.original_faq（完整） | fields.original_text（完整） |
|---|---|---|---|---|
| 0 | text | 甲段。 | 問一。問二。問三。 | — |
| 1 | text | 乙段。 | 問一。問二。問三。 | — |
| 2 | faq | 問一。 | — | 甲段。乙段。 |
| 3 | faq | 問二。 | — | 甲段。乙段。 |
| 4 | faq | 問三。 | — | 甲段。乙段。 |

**兩個獨立 Units：第一筆切 2 段、第二筆切 3 段，共 5 個 Chunk，不跨筆合併**

```json
[
  {
    "text": "甲段。",
    "source_refs": [
      {
        "unit_index": 0,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 0,
        "end": 3
      },
      {
        "unit_index": 0,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "乙段。",
    "source_refs": [
      {
        "unit_index": 0,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 3,
        "end": 6
      },
      {
        "unit_index": 0,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "問一。",
    "source_refs": [
      {
        "unit_index": 1,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 0,
        "end": 3
      },
      {
        "unit_index": 1,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "問二。",
    "source_refs": [
      {
        "unit_index": 1,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 3,
        "end": 6
      },
      {
        "unit_index": 1,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "問三。",
    "source_refs": [
      {
        "unit_index": 1,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 6,
        "end": 9
      },
      {
        "unit_index": 1,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  }
]
```

**Embedding 後：vectors.text 的內容**

以下向量為契約用示意數值，沒有呼叫模型；Profile 與來源欄位必須符合可信 Binding。

```json
{
  "values": [
    0.12,
    -0.08,
    0.31
  ],
  "embedding_profile_id": "embedding-demo-v1",
  "source_field": "text"
}
```

<!-- chunk-report-examples:end -->

## 1. 共用物件

[Schema](../schemas/chunk.schema.json)、[案例](../examples/chunk/cases.json)、[參考驗證](../examples/chunk/contract.py) 共用同一契約。參考工具只組裝已給定切片，不是 Fixed-size／Recursive／Header-aware 的正式實作。

| 必要頂層欄位 | 內容 |
|---|---|
| chunk_id | 非空字串；參考產生規則見 §6 |
| document_id／source_revision | 繼承 ParsedDocument |
| fields | 單一非空 dict；切分片段與明確複製欄位 |
| metadata | 完整繼承合法文件 metadata，加入可信 _rag.source_refs／chunking |
| vectors | Chunker 輸出 {}；Embedding 後為命名向量物件 |

完整 Chunker 輸出必須帶 source_refs 與 chunking；一般傳遞／檢索投影可依契約不帶完整追溯。檢索可省略向量令 vectors={}，不表示刪除已儲存向量。

## 2. 切分與欄位映射

- 預設 split_field=text、output_field=text、copy_fields=[]；來源是 units[i][split_field]，不是 ParsedDocument.fields。
- 每筆 Unit 獨立；每個任務選一個 Component。Fixed-size 依 Token 視窗，Recursive 依分隔符／Token 上限，Header-aware 依 Unit 內 Markdown 標題，超長章節可再 Recursive。
- 所有必要任務套用所有 Units。缺 split 欄位、非字串、全空白、缺明確 copy 欄位、必要 task/unit 零產出都報錯。第一版不新增逐 Unit 路由或可選複製開關。
- 同欄位可切分又完整複製，但目的名稱須不同；進階多任務預設都輸出 text。copy 只讀同一 Unit，不取其他 Unit 補欄位。
- Markdown 標題與內文若被 Parser 分開為不同 Units，Chunker 不跨筆重組。Parser 決定語意單位；Chunker 決定筆內切片。
- 所有輸出欄位名在任務內唯一；copy 欄位可能很長，仍需檢查後續模型輸入上限。

## 3. 來源追溯

| SourceRef 欄位 | 規則 |
|---|---|
| unit_index | 必填整數，0-based；對應本版 ParsedDocument.units 的位置 |
| field／output_field | 必填；來源 Unit key／目的 Chunk.fields key |
| role | split 或 copy |
| start／end | 成對選填；來源 Unit 字串的 Unicode code point 半開範圍 [start,end) |
| chunk_start／chunk_end | 成對選填；輸出字串的本地範圍，用於同一 Unit 的多段來源 |

範例來源：`units[1]["text"][0:3]` 對應 `{unit_index: 1, field: "text", output_field: "text", role: "split", start: 0, end: 3}`。範例使用 Python 位置語意，不能拿 Token 或 UTF-16 offset 直接代入。

同一 Chunk 的來源引用必須指向同一 Unit。copy 表示完整值，不帶文字範圍。移除 schema_id／block_id／block_start／block_end／結構 Location 引用；page 等來源欄位由 Parser 提供並依 copy 設定帶入 fields，不再要求 Chunker 解讀 Block。

來源字串與切片需可還原。Header-aware 若去除標題／重組同一 Unit 文字，需提供對應來源／輸出範圍及 Component 語意驗證；不能捏造連續範圍。這不是新增任意 concat 功能。

## 4. metadata、向量與下游

文件 metadata 全繼承，平台可信欄位由 Engine 控制；unit_index／範圍／fingerprint 自動產生，不列一般 UI 設定。Unit 內可選 unit_id 只是 Parser 欄位，通用 Chunker 不依賴它。

vectors[name] 仍為 `{values: [...], embedding_profile_id: "...", source_field: "text"}`，有限數值、維度／Profile／來源需符合 Binding。Indexing 預設保留完整 fields／metadata／vectors；Rerank／Generation 所需內容在 Chunk 自備，不強制回查 ParsedDocument。

## 5. 有效切分設定與 fingerprint

chunking_spec 是 Engine 解析後的**有效切分執行設定**，不是每個 Chunker class 的固定值，也不是多一份由使用者手填的資料。參考格式名稱為 chunking-spec/0.1-draft；完整 Pipeline Config 的 Schema 仍由 Q-002／Q-004／Q-025 核定。

| 內容 | 納入 fingerprint 的原因 |
|---|---|
| 有序 tasks、唯一 task_id | 決定多欄位輸出順序與任務識別 |
| Component ID／實作版本 | 演算法版本可能影響邊界或結果 |
| split／output／copy 映射 | 決定輸出內容與欄位 |
| 解析後有效參數／Tokenizer ID 與 revision | size／overlap／分隔符／正規化等會影響結果 |

未啟用的方法參數、UI 收合狀態、HTTP 連線、Secret、Run ID、Embedding／Retrieval／Generation 設定不納入。預設值須先補齊；每個任務記錄選用的 Component／版本與有效設定。本文範例 tokenizer 是示意識別，沒有下載或驗證真實 Tokenizer。

同一份解析後設定處理不同文件，fingerprint 相同；同一個 Recursive Component 改欄位、長度或版本，fingerprint 不同。本輪採**整份有效任務計畫的一個 fingerprint**；改其中一個任務會影響這份文件所有 Chunk ID，換取簡單一致的重建語意，暫不承諾逐任務局部保留 ID。

參考計算：json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) → UTF-8 → SHA-256。保留字串原樣，不偷偷做 Unicode normalization。這是 Python 草案規範；跨語言的數字正規化與正式 canonicalization 仍在 Q-007，不能用 Python 內建 hash()。

## 6. Chunk ID、序號與重建

metadata._rag.chunking 記錄 chunking_fingerprint、chunk_ordinal、task_id。實際 spec 存在可追溯 Config／Run，不在每個 Chunk 重複。

- chunk_ordinal 是同一文件本次輸出的**全域** 0-based 序號，依設定任務順序，再依 unit_index，最後依 Unit 內穩定切片順序編排；不是每個欄位各從 0 開始。
- 任務併行時先按上述順序整併，再產生 ID；不能使用完成先後順序。相同輸入的 Component 若不具決定性，須明確宣告並提供可重現策略，不能承諾穩定 ID。
- 參考 chunk_id 為 chk_ 加上 SHA-256；輸入是 document_id、source_revision、chunking_fingerprint、chunk_ordinal 的固定 JSON。完整可執行函式在 contract.py。
- 文件內容變更更新 source_revision；切分設定變更更新 fingerprint；只換 Embedding 或 Inference 設定不改 Chunk ID。相同 revision 不得偷偷表示不同來源內容；來源版本產生與衝突政策仍由 Q-007／Q-008 定案。
- 文件／Chunk ID 作用域為 System；存取必須另帶可信 System 範圍，相同字串不授權跨 System 存取。

重建應先準備新一批完整資料，成功後切換；失敗保留原本可用資料，不搜尋新舊混合版本。這是本輪同意的行為方向；ES／Local Search 的發布、併行更新、部分失敗、舊資料清除與可查詢時點仍在 Q-008～Q-010／Q-015，未實作原子交易。Memory 重啟仍依既有規則重新 Ingestion，不因 fingerprint 就可恢復資料。

## 7. UI 與 Component 開發配套

基本畫面不顯示 split/copy 欄位選擇，直接使用 text。進階才顯示新增任務、來源／輸出映射、附帶欄位與完整原文保留。metadata 繼承、source_refs、fingerprint、ordinal 不提供一般設定選項；預覽／結果詳情可唯讀顯示。

錯誤標示 `[Chunking]` 與具體任務／unit_index／欄位；映射重名、來源不存在、型別／文字格式不合、欄位變更造成失效，皆保留選擇並阻止套用。僅展開進階不改有效設定；手動／AI／Edit／匯出使用相同有效計畫。對應事項集中於 [UIB-013](10_ui_adjustment_backlog.md#uib-013-chunk-contract)，本輪不修改 UI。

Component Developer 仍由 [11](11_component_developer_guide.md) 的流程開發，遵守 ParsedDocument → Chunk 清單的公開邊界；宣告文字格式與 Unit 欄位能力，不能因一般 UI 隱藏欄位就只接受硬編碼 text。Config Schema／UI hints 見 [12](12_component_schema_ui_contract.md)。Runtime 的權限、Context、Batch／Async 與正式類別簽名不由本資料草案代替。

第一版必要切分任務不得默默產生零個 Chunk 後回成功；錯誤顯示來源欄位與 task_id。這是 2026-10-30 後續確認的目標規則，現有參考工具不等於正式 Ingestion／Tokenizer 驗收；批次失敗／提交仍由 Q-009 核定。

## 8. 重現與待核定事項

```bash
python -m pip install -r examples/chunk/requirements.txt
python examples/chunk/build_examples.py
python examples/chunk/render_report.py
python examples/chunk/test_contract.py
```

案例涵蓋單筆、多 Unit 不合併、同筆多任務 2＋3、copy、metadata 及命名向量；負例涵蓋來源越界、跨 Unit、舊結構參照、缺欄位與零產出。測試不呼叫外部服務，也不代替真實切分演算法驗收。

已確認的是六鍵外層、text 預設、進階多任務／複製、來源追溯位置、向量資訊分層及穩定 ID 方向。精確鍵名／nullable／自訂型別與遷移仍以本稿供 M0 審閱；Q-002／Q-003／Q-004／Q-006／Q-007 及索引提交政策不因草案產出而全部結案。

## 9. 後續確認與欄位組裝待討論（2026-10-30）

- D-48 已確認：多任務預設將切分片段寫 fields.text；完整原文複製採不衝突名稱，進階仍可自訂。第一版必要切分欄位缺失／型別錯誤／全空白、明確 copy 欄位缺失或必要任務零產出均明確失敗；可選複製不先擴充。
- Parser 改變需重新處理受影響文件：Parsing → Chunking → Embedding（有配置時）→ Indexing；原始資料可取得時不代表一定要重新上傳。多 Parser 路由的重跑範圍、原始資料保留、重新發布仍須依有效相依與儲存政策決定。這是執行影響說明，沒有新增已實作的重跑／快取能力。
- 重新 Ingestion 與 ID 是否納入解析後輸入內容摘要是不同問題；目前 Hash 規則尚未修改。原始文件版本不變但 Parser 輸出改變時的 ID／index_generation 識別仍在 Q-007／Q-015。
- **待討論，未核定**：切分後 concat 多個欄位、加入固定文字，可候選作為 Chunking 後的共用欄位組裝、在 Embedding 前執行；先不新增 Pipeline Module、不修改 Schema／程式或凍結模板拼字。
- 待確認範圍：是否寫入獨立衍生欄位、來源／衍生血緣與 Token 檢查；與 Embedding Profile 的 encoding prefix、Generation 既有 chunk_template 的分工；模板改動需重跑哪些步驟。不能先把欄位組裝當成已交付能力。
