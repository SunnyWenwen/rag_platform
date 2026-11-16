# System Config、模板與版本

## 草稿、有效設定與部署

Workspace 管理多個 System。System ID、Config Revision、source_revision、索引版本、Runtime Image 版本各自獨立。Builder 草稿可保存未啟用方法；編譯只使用所選方法與 Remote 涵蓋區段，拒絕範圍重疊。切回內建方法時恢復原草稿設定。

同一 Config Revision 在 DEV／FTEST／ENT 沿用相同邏輯設定。端點、Secret 引用、DB／索引實體目標及 Runtime 限制屬環境綁定。變更方法、模型語意、維度或資料欄位產生新 Revision，依相依範圍判斷重建。每次請求採單一有效設定快照；有 queued／running Ingestion 時可存草稿，等該 System 工作完成再啟用新版。

[System Config Schema 草案](../schemas/system_config.draft.schema.json)和[內建／Remote Parsing 對照](../examples/system_config/README.md#可驗證的-local-search-設定)提供發布快照的機器驗證範例。

每個有效節點以 `component_id` 選擇執行方式，並以 `component_version` 固定元件版本。內建元件使用該版本的 Descriptor 驗證參數。Remote API 共用平台保留的 `component_id: remote_api`，由 `service_ref` 選擇外部服務。Builder 設計可用同一個「執行方式」欄位選 Recursive、Fixed-size 或 Remote API。

## 設定位置

| 模組 | 設定與推導 |
|---|---|
| Import | CSV 映射、來源型態、structdata 欄位與批次參數宣告 |
| Parsing | 單選內建方法或 Remote，依選擇推導 Document[] |
| Chunking | 方法、Tokenizer、單一切分來源欄位、一個切分輸出欄位及可選複製欄位 |
| Embedding | 欄位映射、Profile、維度、可選文字組合。Remote 執行 Embedding 時，保留的內建 Chunking 自行指定 Tokenizer |
| Indexing | structdata 搜尋能力覆寫、向量欄位、後端及持久化 |
| Inference Input | 查詢執行參數、型別、必填性與預設值。平台初始化 QueryContext[] |
| Query Transformation | `none` 沿用原始問題；`rewrite` 以 `llm_ref`、`prompt`、`count`、`include_original` 設定單筆或多筆改寫；也可用 Remote |
| Retrieval／Rerank | 內建方法／模型、查詢參數引用、融合與截斷，也可選 Remote 替換。固定 Filter 由 Inference Pipeline 共用 |
| Remote API | 首節點與連續範圍、服務引用、parameters JSON、Ingestion 輸出欄位及向量宣告 |

有效資料欄位由 Import 與後續有效方法推導，外部 Retrieval 沿用這份 System 候選 Schema。整體 Config 包裝依 Q-002 收斂。Prototype 匯出是設定示意。

<a id="data-schema-config"></a>
## 欄位宣告、索引覆寫與發布

| Config 位置 | 設定 |
|---|---|
| `config.pipelines.ingestion.import.parameters.structdata` | 以欄位名稱為 key，宣告 `type`、`required` 以及 `searchable`、`filterable`。兩個搜尋旗標省略時預設為 `false`。 |
| Ingestion 的 Remote `output.structdata` | 以相同格式列出實際輸出。Builder 帶入保留欄位的定義，新增或改寫欄位在此宣告。內建方法輸出由 Descriptor 推導。 |
| `config.pipelines.ingestion.indexing.parameters.structdata_overrides` | 選填，以欄位名為 key。每筆可覆寫 `searchable`、`filterable` 或兩者。未覆寫的屬性繼承上游。 |
| `config.pipelines.inference.fixed_filters` | 選填，以 `AND` 套用於每次 Inference。放在 Pipeline 讓內建及涵蓋 Retrieval 的 Remote 區段共用。Remote 的業務 `parameters` 維持獨立。 |
| Inference Request 的 `filters` | 每次請求選填，與 `fixed_filters` 以 `AND` 合併。兩邊的 `any` 群組各自保有 OR 語意。 |

例如 Import 宣告選填的 `price`，Chunking 複製它，Indexing 開啟 `price.filterable`。最終候選的 `price` 仍是選填數字。IndexBinding 根據生效的 `searchable`／`filterable` 衍生 `fulltext_fields`／`filter_fields`。搜尋與 Filter 引用採 `structdata.<欄位名>`，`group_by` 另可選 `document_id`。

發布先驗 Config 形狀，再依啟用的 Pipeline 推導中間和最終 Schema，最後驗證引用與用途。上游刪除／改名後留下的 Indexing 覆寫、停用的固定 Filter 欄位、不支援的型別用途都要指出設定位置，保留草稿並阻擋發布。未啟用的方法設定可留在草稿。動態 Filter 依請求綁定的 Config Revision 在 Inference Input 重新驗證，無效條件回驗證錯誤。見 [可驗證的設定與請求範例](../examples/system_config/README.md)。

<a id="inference-result-processing"></a>
## Inference 的結果處理

Retrieval 與 Rerank 各自在 Component `parameters` 設定當步分組與 Top N。跨 Query 規則由 Query Transformation 的 UI 編輯，正式 Config 草案規劃放在 `config.pipelines.inference.result_processing.cross_query`，由 Engine 在選定步驟末尾執行。

| 設定 | 內容 |
|---|---|
| Retrieval 參數 | `fulltext_fields`、`vector_fields`、`per_route_k`、多路時必填的同 Query 融合策略、可選 `group_by` 和 `top_n` |
| Rerank 參數 | 評分服務、內容欄位、提問來源、`group_by`、Rerank Top N |
| 跨 Query 規則 | `at` 可選 `after_retrieval` 或 `after_rerank`，另選融合方法、`group_by` 和可選的最終 Top N |

內建 Retrieval 以 `per_route_k` 表示搜尋階段每 Query、每路的上限，多路時必選 RRF 或 Sum Score，交付時每個 Query 只有一份清單。正式設定由使用者選擇融合策略，後端執行方式由 Adapter 負責。策略的專屬參數與預設值留待定義。全文和 Filter 選項依 [欄位總表及 Filter 契約](02_data_contracts.md#data-meta-schema) 推導。

`group_by` 可選 `document_id` 或一個以上有效的 `structdata` 字串欄位，也可以組合使用。選多欄時以欄位值組合作為分組鍵；未設定分組時沿用排序後的清單。當步分組在排序後、當步 Top N 前執行。跨 Query 的融合、分組及 Top N 在該步驟的 Top N 之後執行。

例如 Retrieval 先以 `[structdata.parent_chunk_id]` 收斂每個 Query 的候選，逐 Query Rerank 後，再執行以下跨 Query 規則。

```yaml
result_processing:
  cross_query:
    at: after_rerank
    method: rrf
    rrf_k: 60
    group_by: [document_id]
    top_n: 5
```

這段是正式格式的候選片段。現有 `0.2-draft` 的機器 Schema 尚待加入此規則和逐 Component 參數。Remote 涵蓋整段 Query Transformation → Rerank 時，結果處理由外部服務負責，平台驗證並交付回應。

## 執行參數

Import／Inference Input 各自宣告名稱、型別、必填與預設值。Import 的值放在整批 Ingestion Request 的 `parameters`，Inference 的值放在該次查詢的 `parameters`。Runtime 先檢查型別、套預設及拒絕缺少的必填值。下游用 `{{params.name}}` 引用。Remote parameters JSON 中完整參數引用保留原值型別，例如 `{"top_k":"{{params.top_k}}"}` 在值為整數 5 時解析為 `{"top_k":5}`。執行參數留在呼叫環境，與 Document、metadata、索引內容分開。

認證欄位可填固定 Secret reference 或 `{{params.remote_secret_ref}}`。動態引用必須宣告為 `secret_ref`，由 Runtime 檢查本 System 可使用該引用，再解析成認證 Header。一般業務參數傳入 Remote 的 parameters，實際認證憑證走 Header。

## Admin 全域模板

Admin 以版本化設定檔維護全域模板。目錄提供模板 ID、版本、名稱及可套用的邏輯設定。模板可示範內建方法或整組 Remote 設定。對外連線及 Secret 由套用的 System 依環境補齊。Builder 提供唯讀目錄與「選用模板」，把所選版本複製至目前草稿。User 檢查、編輯、驗證及儲存後生效；Admin 更新模板時，既有 System 持續使用已套用的設定。

## 變更影響

- Import／Parsing／Chunking、文件 Embedding 或 Indexing 若改變已索引的內容、向量或搜尋能力，依 [Runtime 索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle) 判定相容性。不相容的明確更新會刪除舊索引及資料並建立新索引。Builder 用保存的原始資料重新匯入。
- 純查詢參數變更（例如 `top_n`）、不改變輸出語意的執行調整（例如 Embedding batch size），可沿用相容索引。Inference 改用新的搜尋路徑時，仍須確認索引提供其要求的欄位和向量 Profile。
- 外部 Retrieval 使用自身資料，驗證服務契約、回傳候選及後段相依。
- 環境 Endpoint／Secret 更新後重新做連線與相容驗證。修改未啟用的內建草稿不改執行計畫。

範例見 [Remote API fixtures](../examples/user_remote_api/README.md)，舊 D-66／D-67 的候選稿見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。
