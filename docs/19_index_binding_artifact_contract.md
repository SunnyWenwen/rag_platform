# 19 — IndexBinding 與索引格式契約

2026-11-04｜D-55 已確認的開發基準。Model／範例可驗證；正式 SDK、Engine Registry、實體索引讀寫與部署尚未交付。

## 1. 決策與責任

每個 Retrieval System 第一版只有一組邏輯索引，省略 index_ref，不提供多組選擇／管理。多個全文／向量欄位，以及 Component 內部的多個 FAISS Index，可由這組統一管理。

Indexing Component 提供索引描述，Engine 補足可信執行環境、驗證並管理 Binding，Retrieval 透過 Context 取得該 System 唯一的 Binding。Binding 對應整組索引，不為每個 Chunk／Query 各建立一份。一般 Builder User 不另外填 Binding。

| 資訊 | 責任 |
|---|---|
| Component Config | 方法、搜尋／索引欄位、Top K 等處理設定，由 Schema 驗證 |
| 部署設定 | 環境 URL、Secret 引用與資料目標 |
| IndexBinding | 索引格式、定位資訊及經驗證的搜尋能力 |
| RunContext | Engine 提供的必要資源／Binding 引用；與業務 QueryContext 不同 |
| Runtime 狀態 | 初始化／就緒／失敗與資料發布狀態；精確政策依 Q-009／010／017 |

RunContext 的資源由 Config、部署綁定及 Runtime 初始化共同準備，不是 Component Config 的別名。Client、FAISS／BM25 物件留在執行程序中，由 Engine 管生命週期與共用；每次查詢不必重建。Remote Adapter 不將完整 Context／憑證傳給服務，僅傳核定業務資料及明確支援參數。

## 2. 共用 Schema

```python
class VectorIndexBinding(BaseModel):
    embedding_profile_id: str
    source_field: str
    dimensions: int  # 正整數

class IndexBinding(BaseModel):
    artifact_type: str
    target: dict[str, JsonValue] = Field(default_factory=dict)
    fulltext_fields: list[str] = Field(default_factory=list)
    filter_fields: list[str] = Field(default_factory=list)
    vector_bindings: dict[str, VectorIndexBinding] = Field(default_factory=dict)
```

完整嚴格 Model 見 examples/pydantic_contracts/models.py；共用機器 Schema 見 [index_binding.schema.json](../schemas/index_binding.schema.json)。識別／路徑字串非空、維度正整數，欄位清單不重複，未知外層欄位拒絕。artifact_type 必填；其餘四欄可省略，預設為空 object／清單。target 只能含 JSON 資料，不能放 Client、Python class 或任意 import。

| 欄位 | 語意 |
|---|---|
| artifact_type | 已註冊索引格式及版本；識別格式，不是 Component 實作版本 |
| target | 格式專屬的定位資訊，依對應 Schema 再驗證 |
| fulltext_fields | 已提供全文搜尋能力的完整欄位路徑，如 fields.text |
| filter_fields | 已提供 Filter 能力的路徑，如 metadata.department；運算子／缺值政策另依 Q-013 |
| vector_bindings | key=text 表示 vectors.text；Profile、來源欄位及維度必須相容 |

source_field=text 對應 Chunk.fields.text，與既有 DenseVector 一致。Binding 宣告可用能力，Retrieval Config 只能選其中支援者；Chunk 保存某個欄位不代表該欄位可搜尋。宣告、Config、向量與格式需驗證一致，不能只靠宣告通過就假定後端真的有能力。

不保留舊提案的 index_ref、backend、capabilities、system_id、contract_version 或 searchable；共用能力由欄位／向量資訊表達，System 由可信 Context 定位。外層 Schema 版本由 SDK／協定管理，不與 artifact_type 的儲存格式版本混同。index_generation／mapping_version／document_schema_version 等暫不列本版必填，交 Q-007～010／Q-015 決定，沒有取消索引相容性與資料版本管理。

## 3. 索引格式定義與 Developer 配套

artifact_type 對應一份受控註冊的「索引格式定義」，包含 target Schema、資料儲存／讀取規格及能力限制。Indexing／Retrieval 共用這份規格；只有 Binding 無法說明資料布局或如何還原 Chunk。

| 定義 | 第一版示例 |
|---|---|
| builtin.elasticsearch/v1 | target={"collection":"workspace-system-a"}；collection 為 ES 實體索引／約定目標名稱 |
| builtin.local_search/v1 | target={}；唯一索引資源由 System Context 取得，不再引入 resource_ref |

兩個名稱是本次可執行範例的格式識別。target Schema 已提供；完整 ES 儲存 Mapping／Chunk 還原、Local 索引布局／Filter 實作與 Query Encoding 資源介面，仍須於 Q-002／Q-003／Q-011／Q-013 落實並驗收，不能以 target 形狀通過就宣稱格式已完整實作。

相容性流程：核可格式註冊 → Indexing 宣告產出格式 → Retrieval Descriptor 宣告支援格式／版本 → Engine 驗證 target、格式配對、搜尋欄位及 Profile → 檢查 Runtime 就緒／授權 → 執行。未註冊、格式錯版、不相容或未宣告的搜尋欄位應拒絕，不靜默換方法。正式 Descriptor 欄位拼字／版本範圍留 12／Q-019／Q-028。

Developer 可沿用既有格式只開發 Retrieval；若產出新格式，須提供格式規格／Schema，並提供相容 Retrieval 或 Adapter。註冊資料不載入任意前端程式或 import 指令。配套包含：共用 Model、格式規格、Retrieval 範本／資源取得說明及契約／整合測試。

[artifact_definitions.json](../examples/pydantic_contracts/artifact_definitions.json) 示範兩種格式的 target Schema；它不是已定案的 Manifest Meta-schema 或 Registry API。validate_binding_format 是離線註冊／配對驗證參考，不是已交付 Engine。

## 4. 範例

```python
es_binding = IndexBinding(
    artifact_type="builtin.elasticsearch/v1",
    target={"collection": "workspace-system-a"},
    fulltext_fields=["fields.text", "fields.title"],
    filter_fields=["metadata.department"],
    vector_bindings={
        "text": VectorIndexBinding(
            embedding_profile_id="embedding-v1",
            source_field="text",
            dimensions=1024,
        )
    },
)

local_binding = IndexBinding(
    artifact_type="builtin.local_search/v1",
    target={},
    fulltext_fields=["fields.text"],
    vector_bindings=es_binding.vector_bindings,
)
```

同樣的 Profile／欄位可由不同後端實作，但兩種 artifact_type 不能任意交叉讀取。實際宣告 Filter 前需提供可靠候選過濾能力。Profile 相容不只比較維度，仍需配對模型版本及 Query／Document Encoding。

## 5. 狀態、保存與待決邊界

Binding 存在不代表可以查詢。searchable 已移出 Binding；初始化中、恢復中、失敗等由 Runtime 管理。工作 API 是否另外投影 searchable 布林值仍屬 Q-019，不等於把它放回 Binding。

依恢復需要保存或重建可序列化描述，不保存 Client／FAISS Python 物件。Memory 重啟需重新 Ingestion；MongoDB 保存完整 Chunk／vectors，重建本地搜尋資源，完成後才能依發布政策就緒。保存描述不能代替原始資料、Profile、版本及完整性驗證；精確 MongoDB Manifest 與恢復流程仍在 Q-012／Q-015。

本次定案為單組邏輯索引、輕量 Binding、格式專屬 Schema、能力宣告、相容 Retrieval 及狀態分離。完整 Config／SDK、API／Remote 協定、資料更新／原子發布、同分／Filter 語意及版本遷移仍依 08 的 Q-ID，不因本次拍板一併關閉。


## 6. D-58：文件存在／清單與直接刪除

Document 管理使用同一 System 的儲存／索引範圍，不新增第二組 Binding。需依 Artifact 的資料布局，查 document_id 是否有目前有效資料、去重分頁列出全部 ID，以及刪除該文件的 Chunk／vectors、搜尋索引和供恢復的持久副本；不能只刪 FAISS／記憶體索引卻保留 MongoDB 資料，導致重建復活。

預設保存的是 Chunk，document_id 不是 chunk_id／ES _id 的別名；不能只刪掉單一同名 Chunk 就宣稱文件已退役。Runtime 的工作狀態不是文件目錄；清單／存在查詢讀取實際後端，失敗需回錯誤。

新格式／相容 Adapter／私有 Remote 需說明三種管理操作的支援方式與測試，精確介面／能力宣告待 SDK／Manifest 核定；不增加 IndexBinding 根鍵或一般 User 要填的管理參數。API 與語意見 [21 §9](21_runtime_ingestion_inference_api_inventory.md)。
