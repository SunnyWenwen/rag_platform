# 15 — Chunk Contract

更新：2026-11-03（D-52：KISS、追溯選填及 metadata 處理提示）。Chunk **0.2-draft** 保持六個頂層鍵；來源追溯改用 ParsedDocument.units 的位置。舊 0.1 SourceRef 不默默相容。

## 0. 情境與結果摘要

| 情境 | 行為 |
|---|---|
| 預設 | 每個 Unit 的 text 獨立切分，輸出 Chunk.fields.text；copy_fields=[] |
| 多 Unit | 各筆結果串接，2＋3＝5；不合併、不跨 Unit overlap |
| 多欄位任務 | 每個任務遍歷 Units，結果相加，不做笛卡兒積 |
| 保留原文／上下文 | copy 同一 Unit 的欄位；原文另名 original_text，不能覆蓋切片 |
| 來源位置（選用） | Component 可提供 metadata._rag.source_refs：unit_index＋field＋start/end；未提供不報錯、不捏造 |
| Embedding／Indexing | 沿用命名向量物件與完整保存規則 |

<!-- chunk-report-examples:start -->

### 0.2 使用同一份 Schema 的資料例子

以下由共用 cases.json 產生；這組參考工具選擇提供完整追溯，因此例子含 _rag。它們不是所有 Component 的最低交付要求。Hash 是選用參考規則的實際結果；不要求每個 Developer 實作同一演算法。最簡單的三筆 Chunk(...) 例子見 17。

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
| metadata | 繼承合法文件 metadata，可為 {}；Component 可選擇提供 _rag.source_refs／chunking |
| vectors | Chunker 輸出 {}；Embedding 後為命名向量物件 |

正式 Chunker 輸出也不強制提供 _rag、source_refs、fingerprint 或 ordinal；由 Component 決定是否實作。提供標準追溯欄位時才檢查其格式及可取得的來源一致性，未提供不報錯。六個根鍵與文件識別、欄位／向量等既有規則維持。檢索可省略向量令 vectors={}，不表示刪除已儲存向量。

## 2. 切分與欄位映射

- 預設 split_field=text、output_field=text、copy_fields=[]；來源是 units[i][split_field]，不是 ParsedDocument.fields。
- 每筆 Unit 獨立；每個任務選一個 Component。Fixed-size 依 Token 視窗，Recursive 依分隔符／Token 上限，Header-aware 依 Unit 內 Markdown 標題，超長章節可再 Recursive。
- 所有必要任務套用所有 Units。缺 split 欄位、非字串、全空白、缺明確 copy 欄位、必要 task/unit 零產出都報錯。第一版不新增逐 Unit 路由或可選複製開關。
- 同欄位可切分又完整複製，但目的名稱須不同；進階多任務預設都輸出 text。copy 只讀同一 Unit，不取其他 Unit 補欄位。
- Markdown 標題與內文若被 Parser 分開為不同 Units，Chunker 不跨筆重組。Parser 決定語意單位；Chunker 決定筆內切片。
- 所有輸出欄位名在任務內唯一；copy 欄位可能很長，仍需檢查後續模型輸入上限。

## 3. 來源追溯（Component 選用）

本節只規範「有提供」的標準欄位；不要求所有 Component 產生。SDK 可提供組裝／驗證工具，有需要才使用，不強制逐一重寫追溯邏輯。沒有追溯時仍可依 document_id／chunk_id 使用資料，但不保證頁內定位、切片還原或完整來源診斷。

| SourceRef 欄位 | 規則 |
|---|---|
| unit_index | 必填整數，0-based；對應本版 ParsedDocument.units 的位置 |
| field／output_field | 必填；來源 Unit key／目的 Chunk.fields key |
| role | split 或 copy |
| start／end | 成對選填；來源 Unit 字串的 Unicode code point 半開範圍 [start,end) |
| chunk_start／chunk_end | 成對選填；輸出字串的本地範圍，用於同一 Unit 的多段來源 |

範例來源：`units[1]["text"][0:3]` 對應 `{unit_index: 1, field: "text", output_field: "text", role: "split", start: 0, end: 3}`。範例使用 Python 位置語意，不能拿 Token 或 UTF-16 offset 直接代入。

同一 Chunk 的來源引用必須指向同一 Unit。copy 表示完整值，不帶文字範圍。移除 schema_id／block_id／block_start／block_end／結構 Location 引用；page 等來源欄位由 Parser 提供並依 copy 設定帶入 fields，不再要求 Chunker 解讀 Block。

若宣告提供精確切片追溯，來源字串與切片需可還原。Header-aware 去除標題／重組文字時，可以不提供追溯；若提供，須使用正確來源／輸出範圍及對應語意驗證，不能捏造連續範圍。這不是新增任意 concat 功能。

## 4. metadata、向量與下游

文件 metadata 全繼承，平台可信欄位仍由 Engine 控制，不能用業務 metadata 覆寫授權。_rag 選填；unit_index／範圍／fingerprint 有需要時由 Component 或 SDK 輔助產生，不列一般 UI 必填設定。Unit 內可選 unit_id 只是 Parser 欄位，通用 Chunker 不依賴它。

### 4.1 metadata 可以攜帶 Component 的處理提示

metadata 可同時保存描述資訊與 Component 解讀的處理提示，例如：

```python
metadata = {
    "department": "製造部",          # 描述／搜尋過濾
    "chunking_mode": "passthrough", # 本例 Chunker 的文件層處理提示
}
```

chunking_mode 是示範 Component 約定，不是所有 Component 必須認識的全域保留 key。Developer 說明會讀取哪些 key、型別、允許值、未提供時的預設及不支援值的處理；使用者資料也須通過 System 的 metadata Schema（例如 unknown_fields=reject 時要宣告此 string 欄位）。Parser 保留／產生合法提示，Chunker 讀取它，不新增三份共用物件的根欄位。

支援本約定的 Chunker 可直接 `document.metadata.get("chunking_mode", "split")`：缺省正常切分；passthrough 時每 Unit／文字任務完整轉成一筆 Chunk，仍建立 chunk_id、依設定 copy 欄位、繼承 metadata、初始化 vectors={}。不跨 Unit 合併，三個 Units 的單一任務得到三筆，不是整份文件一筆；有多任務仍依任務規則串接。提示不支援時依該 Component 的已宣告行為處理，不能讓平台憑空保證所有 Chunker 都會遵守。

第一版不另建通用條件規則引擎，也不要求 UI 多填一份判斷式；這不是 Config 的任意覆寫入口。固定模型／演算法參數、連線、Secret 仍放 Config／環境綁定，不藏進 metadata。passthrough 不跳過文字／欄位、必要產出及 Embedding 長度檢查；超長仍報錯，不默默截斷。文件提示改變切分結果時需重新 Ingestion，ID／更新處理由選用 Component 的既定策略處理，不要求為此輸出 fingerprint。


### 4.2 向量與下游

vectors[name] 仍為 `{values: [...], embedding_profile_id: "...", source_field: "text"}`，有限數值、維度／Profile／來源需符合 Binding。Indexing 預設保留完整 fields／metadata／vectors；Rerank／檢索結果消費端 所需內容在 Chunk 自備，不強制回查 ParsedDocument。

## 5. 有效切分設定與 fingerprint（選用參考工具）

以下是平台提供的參考 helper 規劃及完整追溯範例所採做法，不是每個 Component 的必要實作；不使用本演算法或不輸出 fingerprint 仍可符合共用 Chunk Contract。

chunking_spec 是 Engine 解析後的**有效切分執行設定**，不是每個 Chunker class 的固定值，也不是多一份由使用者手填的資料。參考格式名稱為 chunking-spec/0.1-draft；完整 Pipeline Config 的 Schema 仍由 Q-002／Q-004／Q-025 核定。

| 內容 | 納入 fingerprint 的原因 |
|---|---|
| 有序 tasks、唯一 task_id | 決定多欄位輸出順序與任務識別 |
| Component ID／實作版本 | 演算法版本可能影響邊界或結果 |
| split／output／copy 映射 | 決定輸出內容與欄位 |
| 解析後有效參數／Tokenizer ID 與 revision | size／overlap／分隔符／正規化等會影響結果 |

未啟用的方法參數、UI 收合狀態、HTTP 連線、Secret、Run ID、Embedding／Retrieval／Rerank 設定不納入。預設值須先補齊；每個任務記錄選用的 Component／版本與有效設定。本文範例 tokenizer 是示意識別，沒有下載或驗證真實 Tokenizer。

同一份解析後設定處理不同文件，fingerprint 相同；同一個 Recursive Component 改欄位、長度或版本，fingerprint 不同。本參考工具採**整份有效任務計畫的一個 fingerprint**；改其中一個任務會影響這份文件所有 Chunk ID，換取簡單一致的重建語意，暫不承諾逐任務局部保留 ID。

參考計算：json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) → UTF-8 → SHA-256。保留字串原樣，不偷偷做 Unicode normalization。這是 Python 草案規範；跨語言的數字正規化與正式 canonicalization 仍在 Q-007，不能用 Python 內建 hash()。

## 6. Chunk ID、序號與重建

chunk_id 仍為必要非空識別，輸出清單內不可重複。可由 Component 或 SDK helper 產生，不強制它必須由 fingerprint／ordinal 計算；穩定性、冪等與更新範圍須依選用實作及 Q-007／Q-008 說明。以下 fingerprint／ordinal／SHA-256 規則只適用採用本參考工具的 Component，不是缺少 _rag 就拒收的理由。

若選擇提供 metadata._rag.chunking，記錄 chunking_fingerprint、chunk_ordinal、task_id，三者遵守該標準區塊格式。實際 spec 存在可追溯 Config／Run，不在每個 Chunk 重複。

- chunk_ordinal 是同一文件本次輸出的**全域** 0-based 序號，依設定任務順序，再依 unit_index，最後依 Unit 內穩定切片順序編排；不是每個欄位各從 0 開始。
- 任務併行時先按上述順序整併，再產生 ID；不能使用完成先後順序。相同輸入的 Component 若不具決定性，須明確宣告並提供可重現策略，不能承諾穩定 ID。
- 參考 chunk_id 為 chk_ 加上 SHA-256；輸入是 document_id、source_revision、chunking_fingerprint、chunk_ordinal 的固定 JSON。完整可執行函式在 contract.py。
- 文件內容變更更新 source_revision；切分設定變更更新 fingerprint；只換 Embedding 或 Inference 設定不改 Chunk ID。相同 revision 不得偷偷表示不同來源內容；來源版本產生與衝突政策仍由 Q-007／Q-008 定案。
- 文件／Chunk ID 作用域為 System；存取必須另帶可信 System 範圍，相同字串不授權跨 System 存取。

重建應先準備新一批完整資料，成功後切換；失敗保留原本可用資料，不搜尋新舊混合版本。這是本輪同意的行為方向；ES／Local Search 的發布、併行更新、部分失敗、舊資料清除與可查詢時點仍在 Q-008～Q-010／Q-015，未實作原子交易。Memory 重啟仍依既有規則重新 Ingestion，不因 fingerprint 就可恢復資料。

## 7. UI 與 Component 開發配套

基本畫面不顯示 split/copy 欄位選擇，直接使用 text。進階才顯示新增任務、來源／輸出映射、附帶欄位與完整原文保留。metadata 繼承保留；source_refs、fingerprint、ordinal 不提供一般必填選項，只在 Component 有提供時唯讀顯示，缺少不當錯誤。Component 支援的 metadata 提示需說明用途／預設，無須新增通用規則表單。

錯誤標示 `[Chunking]` 與具體任務／unit_index／欄位；映射重名、來源不存在、型別／文字格式不合、欄位變更造成失效，皆保留選擇並阻止套用。僅展開進階不改有效設定；手動／AI／Edit／匯出使用相同有效計畫。對應事項集中於 [UIB-013](10_ui_adjustment_backlog.md#uib-013-chunk-contract)，v0.12 已有模擬 UI；真實 Tokenizer／Chunker 待 Engine。

Component Developer 仍由 [11](11_component_developer_guide.md) 的流程開發，遵守 ParsedDocument → Chunk 清單的公開邊界；宣告文字格式與 Unit 欄位能力，不能因一般 UI 隱藏欄位就只接受硬編碼 text。Config Schema／UI hints 見 [12](12_component_schema_ui_contract.md)。Runtime 的權限、Context、Batch／Async 與正式類別簽名不由本資料草案代替。

第一版必要切分任務不得默默產生零個 Chunk 後回成功；錯誤顯示來源欄位與 task_id。這是 2026-10-30 後續確認的目標規則，現有參考工具不等於正式 Ingestion／Tokenizer 驗收；批次失敗／提交仍由 Q-009 核定。

## 8. 重現與待核定事項

```bash
python -m pip install -r examples/chunk/requirements.txt
python examples/chunk/build_examples.py
python examples/chunk/render_report.py
python examples/chunk/test_contract.py
```

案例涵蓋單筆、多 Unit 不合併、同筆多任務 2＋3、copy、metadata 及命名向量；負例涵蓋有提供追溯時的來源越界、跨 Unit、舊結構參照、缺欄位與零產出；另有不帶 _rag 的合法 Chunk／序列案例。嚴格完整追溯檢查只能由測試明確選用，不能成為所有 Component 的驗收門檻。測試不呼叫外部服務，也不代替真實切分演算法驗收。

已確認的是六鍵外層、text 預設、進階多任務／複製、來源追溯位置、向量資訊分層及穩定 ID 方向。精確鍵名／nullable／自訂型別與遷移仍以本稿供 M0 審閱；Q-002／Q-003／Q-004／Q-006／Q-007 及索引提交政策不因草案產出而全部結案。

## 9. 後續確認與欄位組裝（D-53，2026-11-03 已確認功能方向）

- D-48 已確認：多任務預設將切分片段寫 fields.text；完整原文複製採不衝突名稱，進階仍可自訂。第一版必要切分欄位缺失／型別錯誤／全空白、明確 copy 欄位缺失或必要任務零產出均明確失敗；可選複製不先擴充。
- Parser 改變需重新處理受影響文件：Parsing → Chunking → Embedding（有配置時）→ Indexing；原始資料可取得時不代表一定要重新上傳。多 Parser 路由的重跑範圍、原始資料保留、重新發布仍須依有效相依與儲存政策決定。這是執行影響說明，沒有新增已實作的重跑／快取能力。
- 重新 Ingestion 與 ID 是否納入解析後輸入內容摘要是不同問題；目前 Hash 規則尚未修改。原始文件版本不變但 Parser 輸出改變時的 ID／index_generation 識別仍在 Q-007／Q-015。
- D-53 已確認：預設 Embedding Component 提供選用模板組合；預設 Chunker 提供選用原文 Chunk。v0.12 已加入 UI 設定／字串預覽及字元教學案例；Engine 與三份 Ingestion 資料 Schema 維持原狀；不是所有自訂 Component 的必要能力。

<a id="embedding-field-composition"></a>
### 9.1 Embedding 前的欄位模板組合

- 位置：Chunking 後、Embedding 呼叫前，由預設 Embedding Component 前處理，不新增 Pipeline Module。
- UI：提供預設關閉／收合的「內容組合」，啟用後填模板與輸出欄位名稱；預設輸出 fields.embedding_text，既有 Embedding 來源／向量名稱映射仍可設定。
- 支援欄位替換與固定文字，不執行 Python／任意程式，也不呼叫 LLM。第一版以明確的 fields.* 文字欄位為主；缺欄位、型別不符、語法錯誤或輸出命名衝突要報錯，不默默換值或覆寫原 text。
- 先寫入衍生欄位，再走原有映射與模型輸入檢查；新欄位隨 Chunk 一起保存，讓使用者可檢查實際組合的內容。

範例模板（語意已確認；正式設定 Schema／解析器細節待核定）：

```text
標題：{{fields.title}}
內容：{{fields.text}}
```

套用後的 fields：

```python
fields = {
    "title": "設備保養",
    "text": "清潔前先斷電。",
    "embedding_text": "標題：設備保養\n內容：清潔前先斷電。",
}
```

映射可設為 fields.embedding_text → vectors.text；向量 source_field 記 embedding_text，向量名稱不必同名。模型 Profile／document encoding prefix 的規則維持，不能將同一前綴重複加兩次；本模板只用於文件 Chunk，不隱含套用到 Query Encoding。

對最終模型輸入檢查 Token 上限，包含組合內容、Profile 前綴與特殊 Token。模板／輸出欄位／映射等有效變更屬 Ingestion 邏輯變更，需重新組合、Embedding 與 Indexing；是否可重用既有 Chunk 依來源保留能力與 Q-015，不承諾自動局部重跑。一般自訂 Component 只有明確宣告支援時才提供此功能。

<a id="include-original-chunk"></a>
### 9.2 Chunker 額外保留完整原文 Chunk

| 選項 | 行為 |
|---|---|
| 複製原文欄位（既有） | 每筆切片附帶 original_text 等完整欄位，使用不衝突名稱 |
| 額外保留原文 Chunk（新增） | 除切片外，額外輸出一筆完整來源文字的 Chunk；預設關閉 |

「原文」是當前 Unit／切分任務的完整 split_field，不跨 Units 拼成整份文件。額外 Chunk 的主要內容放該任務 output_field（預設 text），title／page 等依相同 copy 規則，繼承合法文件 metadata，建立必要 chunk_id，vectors={}；_rag 仍依 D-52 選填，不新增必要根欄位或 chunk_kind。

若本 Unit／任務已有與完整原文相同的切片，直接沿用，不重複新增。此判斷只在同一 Unit／任務內進行，不對不同文件／Units 任意去重。判斷與輸出順序須穩定；具體 Config 欄位及 ID/helper 的編排細節待核定。

延續 17 的字元教學例（不改正式 Tokenizer 計量）：

| 頁碼 | 一般切片 | 開啟後額外原文 Chunk |
|---|---|---|
| 1：7 字 | 清潔前先斷電。 | 不新增，已有完整相同內容 |
| 2：15 字 | 每月清潔散熱孔並檢查／風扇運轉。 | 每月清潔散熱孔並檢查風扇運轉。 |

因此關閉時 3 筆，開啟時 4 筆。passthrough 已完整轉出原文時，同樣不額外重複新增。多任務仍依各任務處理，不做跨任務／跨 Unit 合併。

新增的原文 Chunk 照常通過 9.1 的內容組合、Embedding 與 Indexing。完整原文可能超過模型輸入上限，須報錯／依既定失敗政策處理，不默默截斷或自動跳過。開關變更會改變 Chunk 集合，需重新 Ingestion；舊資料清除與發布沿用 Q-008～Q-010／Q-015。

### 9.3 待實作與驗收

- UIB-018 記錄模板表單、衍生欄位 Picker／預覽／映射與驗證；UIB-019 記錄原文欄位／原文 Chunk 的獨立選項、去重說明與數量示例。
- Prototype v0.12 已有字串模板／控制項、欄位 Picker 與每 Unit／task 的原文 3／4 筆教學預覽，完成範圍見 10。尚未實作真實 Tokenizer／Chunker、模型長度檢查與模型／DB 串接；17 的三筆教學資料不因此變成正式切分驗收證據。
- 驗收需涵蓋預設關閉、Create／Edit／AI／匯出一致、缺欄位／輸出衝突、衍生來源向量綁定、完整原文重複判斷、單／多 Unit 與多任務、Token 超長及設定變更重跑影響。正式 Schema／模板細節留 Q-002／Q-003／Q-004／Q-015。

