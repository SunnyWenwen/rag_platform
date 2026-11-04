# 17 — Pydantic Contract 與連續範例

2026-11-03｜D-54：簡化 QueryContext 已確認；同日同步 JSON Schema、Model、例子及 Prototype v0.12。這是可執行開發草案，尚非已發布 SDK。2026-11-04 D-55：IndexBinding 已確認為輕量單組描述，見 19；正式 SDK 仍未發布。

## 1. 資料方向與狀態

| 交接 | Python 型別 | 說明 |
|---|---|---|
| API／Import → Parsing | IngestionDocument | 13：單一來源 content／base64／uri |
| Parsing → Chunking | list[ParsedDocument] | 14：平面 units，每筆直接放欄位 |
| Chunking → Embedding → Indexing | list[Chunk] | 15：同一個六鍵物件逐步補 vectors |
| Query Transformation → Retrieval → Rerank → API | list[QueryContext] | 本版確認；result_sets 放在 context 內，沒有另外的外框 |
| Indexing → Retrieval 資源綁定 | IndexBinding | D-55 單組五鍵 Contract；狀態／資源由 Runtime 管理 |

[models.py](../examples/pydantic_contracts/models.py) 為完整可執行定義；下方是易讀欄位視圖，省略驗證函式。Model 嚴格拒絕未知 key，JSON 值須有限。共用 JSON Schema 及 13～15 定義 Ingestion 語意；Inference 見 [05 §4.6](05_data_contracts_search_design.md#query-context-contract)。

[pydantic_contracts.schema.json](../examples/pydantic_contracts/pydantic_contracts.schema.json) 是 $defs 目錄，不是所有 payload 共用的 root。Inference root schema 是 [inference_context.schema.json](../schemas/inference_context.schema.json) 的 array。

## 2. 逐型別範例

先安裝 requirements.txt，再把 typed_examples.py 的範例依序執行。匯入、Annotated／Literal／Field 等別名見 models.py。分頁解析、10 字元切分、向量及分數都是教學資料；沒有執行 Parser／Tokenizer／模型。主案例省略 _rag。

### 2.1 IngestionDocument

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class IngestionDocument(BaseModel):
    document_id: NonEmptyText
    source_revision: NonEmptyText | None = None
    content: NonEmptyText | ContentObject | None = None
    base64: NonEmptyText | None = None
    uri: NonEmptyText | None = None
    media_type: NonEmptyText | None = None
    schema_id: NonEmptyText | None = None
    parsing_profile: NonEmptyText | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

<!-- type-example:IngestionDocument:start -->
```python
ingestion_doc = IngestionDocument(
    document_id="manual-001",
    source_revision="v1",
    content={
        "title": "設備保養手冊",
        "text": "=== PAGE 1 ===\n清潔前先斷電。\n=== PAGE 2 ===\n每月清潔散熱孔並檢查風扇運轉。",
    },
    media_type="application/json",
    metadata={"department": "製造部", "filename": "maintenance.txt"},
)
```
<!-- type-example:IngestionDocument:end -->

### 2.2 ParsedDocument

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class ParsedDocument(BaseModel):
    document_id: NonEmptyText
    source_revision: NonEmptyText
    units: list[dict[str, JsonValue]] = Field(min_length=1)
    metadata: dict[str, JsonValue]
```

<!-- type-example:ParsedDocument:start -->
```python
# 示意 Parser 識別分頁標記後的輸出；不是直接呼叫 Parser。
parsed_doc = ParsedDocument(
    document_id=ingestion_doc.document_id,
    source_revision=ingestion_doc.source_revision,
    units=[
        {"text": "清潔前先斷電。", "title": "設備保養手冊", "page": 1},
        {"text": "每月清潔散熱孔並檢查風扇運轉。", "title": "設備保養手冊", "page": 2},
    ],
    metadata=ingestion_doc.metadata.copy(),
)
```
<!-- type-example:ParsedDocument:end -->

### 2.3 Chunk

承接上面的兩頁 ParsedDocument；7 字元與 15 字元，每 10 字元切一組，overlap=0，明列三筆 Chunk(...)。字元示意不是 Tokenizer。

```python
class Chunk(BaseModel):
    chunk_id: NonEmptyText
    document_id: NonEmptyText
    source_revision: NonEmptyText
    fields: Annotated[dict[NonEmptyText, JsonValue], Field(min_length=1)]
    metadata: dict[str, JsonValue]
    vectors: dict[NonEmptyText, DenseVector]
```

<!-- type-example:Chunk:start -->
```python
# 將上一個 ParsedDocument 逐 Unit、每 10 字元切分，overlap=0。
# 以下直接列出三筆結果；尚未執行 Embedding，主範例省略 _rag。
chunks = [
    Chunk(
        chunk_id="chunk-demo-001",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "清潔前先斷電。",
            "title": "設備保養手冊",
            "page": 1,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
    Chunk(
        chunk_id="chunk-demo-002",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "每月清潔散熱孔並檢查",
            "title": "設備保養手冊",
            "page": 2,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
    Chunk(
        chunk_id="chunk-demo-003",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "風扇運轉。",
            "title": "設備保養手冊",
            "page": 2,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
]

# 後面的 ResultItem 等範例，以第一筆 Chunk 示範。
chunk = chunks[0]
```
<!-- type-example:Chunk:end -->

### 2.4 DenseVector

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class DenseVector(BaseModel):
    values: Annotated[list[FiniteFloat], Field(min_length=1)]
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText
```

<!-- type-example:DenseVector:start -->
```python
vector = DenseVector(
    values=[0.1, 0.2, 0.3],  # 教學用三維值；正式維度由模型決定。
    embedding_profile_id="embedding-demo-v1",
    source_field="text",  # 來源是 Chunk.fields.text。
)
```
<!-- type-example:DenseVector:end -->

### 2.5 FilterCondition

eq 必須為字串；in 必須為非空字串陣列，並由 Runtime 驗證欄位有相容 Filter 索引。

```python
class FilterCondition(BaseModel):
    field: NonEmptyText
    operator: Literal["eq", "in"]
    value: str | list[str]
```

<!-- type-example:FilterCondition:start -->
```python
filter_condition = FilterCondition(
    field="metadata.department", operator="eq", value="製造部",
)
```
<!-- type-example:FilterCondition:end -->

### 2.6 ResultItem

score 選填，可缺省／null；只有數值時為越大越好。RRF 直接讀 items 的位置，不能把名次塞進 score 當相關分數。

```python
class ResultItem(BaseModel):
    chunk: Chunk
    score: FiniteFloat | None = None
```

<!-- type-example:ResultItem:start -->
```python
result_item = ResultItem(chunk=chunk, score=0.95)
# 沒有數值分數的後端也合法：ResultItem(chunk=chunk)。RRF 讀取陣列位置。
```
<!-- type-example:ResultItem:end -->

### 2.7 ResultSet

key 在同一 context 內唯一，可對應 Config 路徑或群組；items 順序就是排名。

```python
class ResultSet(BaseModel):
    key: NonEmptyText
    items: list[ResultItem] = Field(default_factory=list)
```

<!-- type-example:ResultSet:start -->
```python
result_set = ResultSet(key="merged", items=[result_item])
# key 是 Config 可引用的搜尋路徑／群組；items 順序就是排名。
```
<!-- type-example:ResultSet:end -->

### 2.8 QueryContext

filters／metadata／result_sets 可省略，預設 []／{}／[]。Rewrite 複製 filters／metadata；只留目前有效清單。

```python
class QueryContext(BaseModel):
    ori_query: NonEmptyText
    query: NonEmptyText
    filters: list[FilterCondition] = Field(default_factory=list)
    result_sets: list[ResultSet] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

<!-- type-example:QueryContext:start -->
```python
query_context = QueryContext(
    ori_query="清潔前應注意什麼？",
    query="清潔前應注意什麼？",
    filters=[filter_condition],
    result_sets=[result_set],
    metadata={"language": "zh-TW", "session_tag": "demo"},
)
```
<!-- type-example:QueryContext:end -->

### 2.9 ChunkSourceRef

選填的文件來源位置，與已刪除的 ResultItem 分數血緣不同。Component 沒提供時不捏造，也不阻擋處理。

```python
class ChunkSourceRef(BaseModel):
    unit_index: NonNegativeInt
    field: NonEmptyText
    output_field: NonEmptyText
    role: Literal["split", "copy"]
    start: NonNegativeInt | None = None
    end: NonNegativeInt | None = None
    chunk_start: NonNegativeInt | None = None
    chunk_end: NonNegativeInt | None = None
```

<!-- type-example:ChunkSourceRef:start -->
```python
chunk_source_ref = ChunkSourceRef(
    unit_index=0,
    field="text",
    output_field="text",
    role="split",
    start=0,
    end=len(parsed_doc.units[0]["text"]),
)
```
<!-- type-example:ChunkSourceRef:end -->

### 2.10 ChunkingIdentity

fingerprint／ordinal／task_id 只在 Component 選擇提供時存在；SDK helper 可協助，不強迫所有 Component 實作。

```python
class ChunkingIdentity(BaseModel):
    chunking_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    chunk_ordinal: NonNegativeInt
    task_id: NonEmptyText
```

<!-- type-example:ChunkingIdentity:start -->
```python
chunking_identity = ChunkingIdentity(
    chunking_fingerprint="0" * 64,  # 實際值須依 15 的規則產生。
    chunk_ordinal=0,  # 此切分任務中的第 1 筆，從 0 起算。
    task_id="text",  # 此例設定的切分任務識別。
)
```
<!-- type-example:ChunkingIdentity:end -->

### 2.11 RagMetadata

Chunk.metadata._rag 的選填進階視圖，不改名、不增加必填頂層 key。

```python
class RagMetadata(BaseModel):
    source_refs: Annotated[list[ChunkSourceRef], Field(min_length=1)] | None = None
    chunking: ChunkingIdentity | None = None
```

<!-- type-example:RagMetadata:start -->
```python
rag_metadata = RagMetadata(
    source_refs=[
        chunk_source_ref,
        ChunkSourceRef(unit_index=0, field="title", output_field="title", role="copy"),
        ChunkSourceRef(unit_index=0, field="page", output_field="page", role="copy"),
    ],
    chunking=chunking_identity,
)
# 追溯型別的獨立進階範例；主流程 Chunk 範例省略 _rag 以利說明。
```
<!-- type-example:RagMetadata:end -->

### 2.12 VectorIndexBinding

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class VectorIndexBinding(BaseModel):
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText
    dimensions: PositiveInt
```

<!-- type-example:VectorIndexBinding:start -->
```python
vector_binding = VectorIndexBinding(
    embedding_profile_id=vector.embedding_profile_id,
    source_field="text",
    dimensions=3,  # 必須和 values 長度及模型輸出一致。
)
```
<!-- type-example:VectorIndexBinding:end -->

### 2.13 IndexBinding

D-55 已確認。每 System 一組，無 index_ref／searchable；target 按 artifact_type 對應 Schema 驗證，Retrieval 須宣告相容格式，且只可搜尋宣告能力。完整語意與 ES／Local／客製配套見 [19 IndexBinding 與索引格式契約](19_index_binding_artifact_contract.md)。

```python
class IndexBinding(BaseModel):
    artifact_type: NonEmptyText
    target: dict[str, JsonValue] = Field(default_factory=dict)
    fulltext_fields: list[NonEmptyText] = Field(default_factory=list)
    filter_fields: list[NonEmptyText] = Field(default_factory=list)
    vector_bindings: dict[NonEmptyText, VectorIndexBinding] = Field(default_factory=dict)
```

<!-- type-example:IndexBinding:start -->
```python
index_binding = IndexBinding(
    artifact_type="builtin.elasticsearch/v1",
    target={"collection": "workspace-demo-system-a"},
    fulltext_fields=["fields.text"],
    filter_fields=["metadata.department"],
    vector_bindings={"text": vector_binding},
)
validate_binding_format(index_binding, ["builtin.elasticsearch/v1"])
```
<!-- type-example:IndexBinding:end -->

target Schema 與相容性驗證參考見 models.py／artifact_definitions.json；共用外層見 schemas/index_binding.schema.json。Schema 通過不是後端存在／可查詢的證據。舊 index-binding-0.1-proposal payload 需明確遷移，不靜默接受已刪鍵。

### 2.14 ModuleResult

只示範本地 Parser 的成功包裝。Remote Parser body 是 ParsedDocument[]；推論業務 body 直接 QueryContext[]，不能再加 data 外框。

```python
class ModuleResult (Generic[T]):
    data: T
```

<!-- type-example:ModuleResult:start -->
```python
# 以 Parser 的本地呼叫為例；同一個 API 請求也可能解析出多份文件。
module_result = ModuleResult[list[ParsedDocument]](data=[parsed_doc])
parser_http_body = [doc.to_payload() for doc in module_result.data]
# Remote Parser HTTP 回傳 parser_http_body；本地 Adapter 再包成 ModuleResult。
```
<!-- type-example:ModuleResult:end -->

## 3. 推論直接傳 list

```python
from pydantic import TypeAdapter
from models import QueryContext

contexts: list[QueryContext] = [query_context]
wire = [context.model_dump(mode="json") for context in contexts]
validated = TypeAdapter(list[QueryContext]).validate_python(wire)
```

Query Transformation、Retrieval、Rerank 均用同型別，更新 filters／metadata／目前清單後傳出。Rerank 覆寫 score，結果排序後取 Top N；RRF 以 enumerate(items, start=1) 取得名次，輸出融合 score。Sum Score 必須有完整可比分數。跨 Query 僅限同次請求、相同 filters；本版 metadata 不同時拒絕合併，避免靜默覆寫。歷史或效能資料寫 Logs。

這版取代舊 InferenceState：不接受舊 wrapper，不保留 active_*、query/result IDs、operation、score_kind/order 或 ResultItem.rank/source_refs。Chunk 的選填 _rag 仍保留。

## 4. 驗證與限制

```bash
python -m pip install -r examples/pydantic_contracts/requirements.txt
python examples/pydantic_contracts/build_examples.py
python examples/pydantic_contracts/export_schemas.py
python examples/pydantic_contracts/test_models.py
python examples/inference/python_example.py
```

[examples.json](../examples/pydantic_contracts/examples.json) 提供 14 個型別例子、三筆 Chunk、QueryContext[] 與 Parser 成功包裝。五組完整推論快照見 examples/inference。DTO 型別檢查不代替業務規則：索引可用性、授權、向量 Profile、分數可比性、模型上限仍需 Runtime／Adapter 驗證。正式 SDK 版本與錯誤政策由 08 追蹤。
