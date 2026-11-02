# 17 — 03 圖中的 Pydantic Contract 草案

2026-11-02｜可執行型別草案，尚非正式 SDK；本次不修改既有共用 JSON Schema、UI 或 Engine。

## 1. 先看物件與責任

搭配 [03 Module／Component 圖](../diagrams/03_module_component_concept.md) 閱讀。

| 圖上的名稱 | Python 型別 | 定義狀態 |
|---|---|---|
| IngestionDocument | IngestionDocument | 對齊 13／既有 JSON Schema；API、Import、Parser 共用 |
| ParsedDocument[] | list[ParsedDocument] | 對齊 14／0.2；units 維持平面 list[dict] |
| Chunk[] | list[Chunk] | 對齊 15／0.2；Embedding 前後使用同一物件 |
| IndexBinding | IndexBinding | **欄位新提案，待確認**；原先 05 只有責任描述 |
| QueryContext[] | list[QueryContext] | 對齊既有 inference-0.2-draft |
| ResultSet[] | list[ResultSet] | 對齊既有 inference-0.2-draft；items 包含 ResultItem／Chunk |
| 推論外框 | InferenceState | 保留原 Query、結果清單與目前有效選擇 |
| 本地呼叫包裝 | ModuleResult[T] | 本例只示範成功回傳的 data；正式 metrics／errors／生命週期仍待定 |

完整可執行程式：[models.py](../examples/pydantic_contracts/models.py)。

可檢視的 JSON Schema 定義目錄：[pydantic_contracts.schema.json](../examples/pydantic_contracts/pydantic_contracts.schema.json)；它是 **$defs 型別目錄**，不是一個可套用全部 payload 的 root Schema。單一型別須選相應 $defs／Pydantic Model。

資料範例：[examples.json](../examples/pydantic_contracts/examples.json)，包含多頁 Input／ParsedDocument、Embedding 前後 Chunk、IndexBinding 提案、QueryContext、InferenceState 與成功 ModuleResult。Chunk ID／fingerprint／向量／分數為示意，不代表已執行 Tokenizer、Embedding、Indexing 或 Rerank。

## 2. 欄位視圖

以下省略共同 Base、validator 與部分 Schema 描述，方便對照；**完整驗證行為以 models.py 為準**。NonEmptyText 是非空 string，NonNegativeInt／PositiveInt 是整數範圍，FiniteFloat 禁止 NaN／Infinity。額外欄位原則上拒絕；units／fields／metadata 等明確的業務容器保留合法 JSON 彈性。

### 2.1 IngestionDocument：來源三選一

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

content／base64／uri 恰好一個；可選根欄位可省略但不接受明確 null。metadata 省略時補 {}；source_revision 的自動產生政策仍待 Q-007。URI 協定／資源取得、Base64 解碼與格式能力由相容 Parser／resolver 檢查。

### 2.2 ParsedDocument：Parser 的統一輸出

```python
class ParsedDocument(BaseModel):
    document_id: NonEmptyText
    source_revision: NonEmptyText
    units: list[dict[str, JsonValue]] = Field(min_length=1)
    metadata: dict[str, JsonValue]
```

units 每筆直接放內容 key，不包 fields、不要求 unit_id、不引入額外的 Page 型別。一般文字流程預設用 text；若提供 text，它必須是 string。其他用途仍依 Parser／System 欄位 Schema 限縮型別；JsonValue 不表示任意物件都能送去 Chunking／Embedding。

### 2.3 Chunk 與 DenseVector：同一物件逐步補向量

```python
class DenseVector(BaseModel):
    values: Annotated[list[FiniteFloat], Field(min_length=1)]
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText
```

```python
class Chunk(BaseModel):
    chunk_id: NonEmptyText
    document_id: NonEmptyText
    source_revision: NonEmptyText
    fields: Annotated[dict[NonEmptyText, JsonValue], Field(min_length=1)]
    metadata: dict[str, JsonValue]
    vectors: dict[NonEmptyText, DenseVector]
```

Chunker 輸出 vectors={}；Embedding 將命名向量寫回 vectors，例如 vectors.text。檢索投影也可以 vectors={}，不代表刪掉索引中已保存的向量。

Chunk.metadata 仍是 dict；若有 _rag，額外由 RagMetadata 驗證 source_refs／chunking。這是保留既有六鍵形狀，不新增頂層資料。純文字／向量欄位的使用條件、Tokenizer、追溯還原、ID／fingerprint 與可信 metadata 授權，仍需 Component／Engine 驗證。

### 2.4 QueryContext／ResultSet／ResultItem 與外框

```python
class ResultSourceRef(BaseModel):
    result_set_id: NonEmptyText
    chunk_id: NonEmptyText
```

```python
class ResultItem(BaseModel):
    chunk: Chunk
    score: FiniteFloat
    rank: PositiveInt
    source_refs: list[ResultSourceRef]
```

```python
class RetrievalSource(BaseModel):
    route_id: NonEmptyText
    index_ref: NonEmptyText
    field_paths: Annotated[list[NonEmptyText], Field(min_length=1)]
```

```python
class Operation(BaseModel):
    method: NonEmptyText
    parameters: dict[str, JsonValue]
    model_ref: NonEmptyText | None
    scoring_query_id: NonEmptyText | None
```

```python
class ResultSet(BaseModel):
    result_set_id: NonEmptyText
    stage: Literal['retrieval', 'merge', 'top_n', 'model_score']
    input_result_set_ids: list[NonEmptyText]
    source: RetrievalSource | None
    operation: Operation
    score_kind: NonEmptyText
    score_order: Literal['higher_is_better', 'lower_is_better']
    items: list[ResultItem]
```

```python
class QueryContext(BaseModel):
    query_id: NonEmptyText
    query: NonEmptyText
    ori_query_id: NonEmptyText
    ori_query: NonEmptyText
    source_query_ids: list[NonEmptyText]
    result_sets: list[ResultSet]
    active_result_set_ids: list[NonEmptyText]
```

```python
class InferenceState(BaseModel):
    contract_version: Literal['inference-0.2-draft']
    query_contexts: Annotated[list[QueryContext], Field(min_length=1)]
    active_query_ids: list[NonEmptyText]
```

- stage 只有 retrieval／merge／top_n／model_score，排序是各動作的共同收尾，不另加 sort Stage。
- 初次 retrieval 需要 source；input_result_set_ids 與每個 item.source_refs 為空。後續處理 source=null、需要上游清單引用，且每個輸出 item 要有來源追溯。
- Operation.model_ref、scoring_query_id 及 ResultSet.source 是**必填但可為 null**；與可省略／不接受 null 的 Ingestion 選填欄位不同。
- QueryContext 保留 ori_query／ori_query_id；active IDs 選有效清單，不刪掉歷史清單。跨 Query 的合併仍依有效計畫執行，不由型別本身決定。
- source 的 index_ref 對回可信 IndexBinding.index_ref；不能信任使用者自行填 system_id／index_ref 就取得索引權限。
- 原始 Query 來源、跨 Query／ResultSet 的完整血緣解析、score 可比性與 Fusion 計畫仍由 Engine 驗證。模型內已檢查本地 active IDs、唯一識別及 stage 基本規則；不是完整 Engine 的替代品。

## 3. 兩種 SourceRef 不要混用

| 型別 | 放哪裡 | 追溯內容 |
|---|---|---|
| ChunkSourceRef | Chunk.metadata._rag.source_refs | ParsedDocument 的 unit_index、來源欄位及字元範圍 |
| ResultSourceRef | ResultItem.source_refs | 上游 result_set_id／chunk_id，追溯分數與候選來源 |

```python
class ChunkSourceRef(BaseModel):
    unit_index: NonNegativeInt
    field: NonEmptyText
    output_field: NonEmptyText
    role: Literal['split', 'copy']
    start: NonNegativeInt | None = None
    end: NonNegativeInt | None = None
    chunk_start: NonNegativeInt | None = None
    chunk_end: NonNegativeInt | None = None
```

```python
class ChunkingIdentity(BaseModel):
    chunking_fingerprint: Annotated[str, Field(pattern='^[0-9a-f]{64}$')]
    chunk_ordinal: NonNegativeInt
    task_id: NonEmptyText
```

```python
class RagMetadata(BaseModel):
    source_refs: Annotated[list[ChunkSourceRef], Field(min_length=1)] | None = None
    chunking: ChunkingIdentity | None = None
```

SourceRef 的 start/end、chunk_start/chunk_end 成對提供，以 Unicode code point、0-based 半開區間表示；未提供不序列化成 null。完整 Chunker 輸出必須依 15 帶追溯／chunking、vectors={}；一般傳遞 DTO／檢索投影的要求較少，不能只通過 Chunk Model 就宣稱完成整個 Chunker 驗收。

## 4. IndexBinding：這版新增的欄位提案

**以下為待確認提案，尚未改寫 05 或正式 Runtime 介面。**它是 Indexing 結果與 Retrieval 的可信綁定描述，不裝入 ES Client、FAISS Index Python 物件、連線密碼或 Secret 值。

```python
class VectorIndexBinding(BaseModel):
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText
    dimensions: PositiveInt
```

```python
class IndexBinding(BaseModel):
    contract_version: Literal['index-binding-0.1-proposal']
    index_ref: NonEmptyText
    system_id: NonEmptyText
    backend: Literal['elasticsearch', 'local_search']
    collection: NonEmptyText
    index_generation: NonEmptyText
    mapping_version: NonEmptyText
    document_schema_version: NonEmptyText
    capabilities: list[Literal['fulltext', 'dense_vector', 'filter']]
    fulltext_fields: list[NonEmptyText]
    filter_fields: list[NonEmptyText]
    vector_bindings: dict[NonEmptyText, VectorIndexBinding]
    searchable: bool
```

| 欄位群 | 用途 |
|---|---|
| index_ref／system_id | 穩定邏輯引用與 System 作用範圍；授權仍來自可信 Context |
| backend／collection | 後端與環境解析後的目標集合；不因此改變邏輯 Config |
| index_generation／mapping_version／document_schema_version | 資料、Mapping 與欄位 Schema 的可追溯版本 |
| capabilities／fulltext_fields／filter_fields | 可搜尋／過濾能力與欄位；使用完整路徑，例如 fields.text |
| vector_bindings | key 是 vectors 中的名稱，例如 text；綁定 Profile、Chunk.fields 的來源 key 與維度 |
| searchable | 此 Binding 的可搜尋狀態快照，不是永遠有效或授權保證 |

backend 首版示範 elasticsearch／local_search；不同索引 artifact、可變 alias、切換原子性、併發版本、空索引、ready 狀態、跨 System 與持久化恢復仍待既有 Q-ID 決策。尚未存在實作的版本 ID 不應用任意值假裝已完成版本管理。

## 5. ModuleResult 與序列化

```python
class ModuleResult(BaseModel, Generic[T]):
    data: T
```

這是成功路徑的本地型別示例，例如 ModuleResult[list[ParsedDocument]]。Remote Parser 範例的 HTTP 成功 body 仍直接是 list[ParsedDocument]，由 Retrieval Builder 的 Adapter 再包成本地 ModuleResult；不因增加這份彙整就改成傳送整個 ModuleResult／RunContext。

使用 `.to_payload()` 產生符合省略規則的 JSON dict；它使用 by_alias=True、exclude_unset=True，不把未設定的 Python None 變成禁止的 wire null。不要全域 exclude_none=True，因為 Operation 等欄位明確要求保留 null。

可選的輔助檢查：validate_result_order() 驗證連續 rank 與分數排序；validate_chunk_binding() 驗證完整待儲存 Chunk 的向量 Profile／來源／維度。後者不拿來判斷省略向量的檢索投影是否完整，也不代替來源授權。

## 6. 驗證與使用

本例只依賴 Pydantic，測試另需 jsonschema；沒有 FastAPI、HTTP Client 或完整 Engine 相依。repo 根目錄執行：

```bash
python -m venv .venv-contracts
.venv-contracts/bin/pip install -r examples/pydantic_contracts/requirements.txt
.venv-contracts/bin/python examples/pydantic_contracts/test_models.py
.venv-contracts/bin/python examples/pydantic_contracts/export_schemas.py
.venv-contracts/bin/python examples/pydantic_contracts/build_examples.py
```

```python
from models import InferenceState, ParsedDocument

# 程式位於同資料夾，或先將該目錄納入 Python import path。
document = ParsedDocument.model_validate({
    "document_id": "manual-001", "source_revision": "v1",
    "units": [{"text": "第一頁內容", "page": 1}], "metadata": {},
})
payload = document.to_payload()
```

驗證覆蓋既有 ParsedDocument／Chunk／5 份推論情境的 round-trip，以及缺欄位、來源三選一、null、型別、向量、來源引用、stage、active IDs、排序與 IndexBinding 提案反例。資料驗證不等於已執行搜尋／模型／重建／部署。

**相容性說明：**共用物件形狀以 schemas/ 與 13～15 為準；這份 Pydantic 集合是可執行草案，部分 validator 增加跨欄位／語意檢查。自動匯出的 JSON Schema 不會完整表達所有 custom validator，不能用生成 Schema 單獨取代語意驗證。IndexBinding／ModuleResult 的正式版本、SDK 模組路徑與封裝仍待核定；本次沒有發布新 SDK，也沒有遷移 16 的既有教學程式。
