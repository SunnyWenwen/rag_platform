# System Config、模板與版本

## 草稿、有效設定與部署

Workspace 管理多個 System。System ID、Config Revision、source_revision、索引版本、Runtime Image 版本各自獨立。Builder 草稿可保存未啟用方法；編譯只使用所選方法與 Remote 涵蓋區段，拒絕範圍重疊。切回內建方法時恢復原草稿設定。

同一 Config Revision 在 DEV／FTEST／ENT 沿用相同邏輯設定。端點、Secret 的實際值、DB／索引實體目標及 Runtime 限制屬環境綁定。變更方法、模型語意、維度或資料欄位產生新 Revision，依相依範圍判斷重建。每次請求採單一有效設定快照；有 queued／running Ingestion 時可存草稿，等該 System 工作完成再啟用新版。

[System Config Schema 草案](../schemas/system_config.draft.schema.json)和[內建／Remote Parsing 對照](../examples/system_config/README.md#可驗證的-local-search-設定)提供發布快照的機器驗證範例。

每個有效節點以 `component_id` 選擇執行方式，並以 `component_version` 固定元件版本。內建元件使用該版本的 Descriptor 驗證參數。Remote API 共用平台保留的 `component_id: remote_api`，由 `service_ref` 選擇外部服務。Builder 設計可用同一個「執行方式」欄位選 Recursive、Fixed-size 或 Remote API。

<a id="config-fields"></a>
### Config 快照與節點欄位

| 路徑 | 責任與語意 |
|---|---|
| `system_id` | 快照所屬的 System。HTTP 驗證和套用時由路徑提供。 |
| `config_revision` | Builder 指派的發布版本。新版本在套用請求傳入，草稿驗證使用自己的 `draft_revision`。 |
| `config` | 有效邏輯設定。Runtime 驗證與套用請求直接帶這個內層物件。 |
| `config.contract_version` | 此 Config 的格式版本，現行為 `0.2-draft`。 |
| `config.secret` | 選填的 System 級 KV。Builder 啟用測試時提供字串值，部署匯出保留 Key 並將值設為 `null`。見 [System Secret](#system-secret)。 |
| `config.pipelines` | 包含 `ingestion`、`inference`。每個有效模組對應一個節點。 |
| 節點的 `component_id`、`component_version`、`parameters` | 分別選方法、固定版本、保存該方法的設定。個別參數由所選 Descriptor 的 `parameters_schema` 定義。 |
| Remote 節點的 `through`、`service_ref`、`auth`、`output` | `through` 含括區段最後一個模組，首節點由 Pipeline 上的 key 指定。 `service_ref` 引用環境的外部服務綁定。選填的 `auth.bearer_token` 使用 `{{KEY}}`。Ingestion Remote 另須以 `output` 宣告適用的 `structdata` 或 `vectors`，Inference 依 System 的有效候選 Schema 驗證。 |

發布時依固定的 Pipeline 順序核對節點。Remote 區段涵蓋的後續節點在有效設定中省略，由首節點涵蓋。JSON Schema 驗證結構，編譯器檢查覆蓋是否完整且無重疊、元件版本、欄位相依及引用。見 [Runtime 驗證契約](06_runtime_api_and_deployment.md#config-validation-api)。

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
| 其他設定 → Secret | 管理同一 System 各 Module 可引用的 KV；輸入 DEV 測試值。 |
| Remote API | 首節點與連續範圍、服務引用、parameters JSON、Ingestion 輸出欄位及向量宣告 |

有效資料欄位由 Import 與後續有效方法推導，外部 Retrieval 沿用這份 System 候選 Schema。W1 開發依 [Schema 與範例](../examples/system_config/README.md)。後續版本凍結和遷移依 [Q-002](08_plan_and_decisions.md#q-002)，部署 Bundle 依 [Q-021](08_plan_and_decisions.md#q-021)。Prototype 匯出用於示意。

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

Retrieval 與 Rerank 各自在 Component `parameters` 設定當步分組與 Top N。跨 Query 融合由 Query Transformation 配置。內建 `rewrite` 的發布欄位位於 `config.pipelines.inference.query_transformation.parameters`，沿用 [Rewrite Descriptor](../examples/system_config/rewrite.descriptor.json) 的欄位和值。

| 設定 | 內容 |
|---|---|
| Retrieval 參數 | `fulltext_fields`、`vector_fields`、`per_route_k`、多路時必填的同 Query 融合策略、可選 `group_by` 和 `top_n` |
| Rerank 參數 | 評分服務、內容欄位、提問來源、`group_by`、Rerank Top N |
| 跨 Query 融合時點 | `cross_query_at` 可選 `"Retrieval 後"` 或 `"Rerank 後"`，預設 `"Retrieval 後"`。 |
| 跨 Query 融合策略 | `cross_query_method` 可選 `"RRF"` 或 `"Sum Score"`，預設 `"RRF"`。 |
| 跨 Query 分組與截斷 | 選填 `cross_query_group_by` 和 `cross_query_top_n`。 |

內建 Retrieval 的全文與向量欄位皆可多選，每個向量欄位依 IndexBinding 的 `embedding_profile_id` 決定 Query Encoder。`per_route_k` 是每個 Query 在個別路徑的搜尋上限。多路時必選 RRF 或 Sum Score，交付時每個 Query 只有一份清單。Adapter 負責執行選定的策略。策略的專屬參數與預設值留待定義。全文和 Filter 選項依 [欄位總表及 Filter 契約](02_data_contracts.md#data-meta-schema) 推導。

`group_by` 可選 `document_id` 或一個以上有效的 `structdata` 字串欄位，也可以組合使用。選多欄時以欄位值組合作為分組鍵；未設定分組時沿用排序後的清單。當步分組在排序後、當步 Top N 前執行。跨 Query 的融合、分組及 Top N 在該步驟的 Top N 之後執行。

Builder 依 `count + (include_original ? 1 : 0)` 決定是否顯示跨 Query 設定。Engine 依進入平台結果處理的有效 Query 數執行，達兩個即啟用融合，省略時點或策略時套用上表預設。單 Query 略過跨 Query 融合；表單切回多 Query 時可恢復草稿中的原設定。

以下是 `config.pipelines.inference` 的 Query Transformation 節點片段。它產生兩個改寫 Query 並保留原始 Query，三份清單逐 Query Rerank 後再融合。

```yaml
query_transformation:
  component_id: rewrite
  component_version: "1.0.0"
  parameters:
    llm_ref: default-llm
    prompt: "為 {{query}} 產生 {{count}} 個查詢。"
    count: 2
    include_original: true
    cross_query_at: "Rerank 後"
    cross_query_method: "RRF"
    cross_query_group_by: [document_id]
    cross_query_top_n: 5
```

W1 HTTP 範例採單 Query，多 Query 執行與融合留在 M2 驗收。Remote 區段涵蓋結果處理時，由外部服務負責該區段的融合。Remote 只產生多 Query 並交由平台融合時，平台設定如何存於 Query Transformation 節點，需依 [Q-014](08_plan_and_decisions.md#q-014)／[Q-028](08_plan_and_decisions.md#q-028) 定義，Remote 的 `parameters` 仍承載外部服務自身的參數。

## 執行參數

Import／Inference Input 各自宣告名稱、型別、必填與預設值。Import 的值放在整批 Ingestion Request 的 `parameters`，Inference 的值放在該次查詢的 `parameters`。執行參數留在呼叫環境，與 Document、metadata、索引內容分開。

現行表單在 `import.parameters.request_parameters` 或 `inference_input.parameters.request_parameters` 宣告。每列包含 `name`、`type`（`string`、`integer`、`number`、`boolean`、`array`、`object`）、`required` 及選填的 `default_value`。`default_value` 存 JSON 文字，例如 `{"default_value":"\"zh-TW\""}`。Runtime 驗證已宣告的 Request 參數、套用宣告的預設值，並拒絕缺少必填項目或型別不符的請求。

<a id="parameter-references"></a>
### 共用引用語法

Builder 在支援引用的欄位統一填 `{{KEYNAME}}`。引用名稱採 `[A-Za-z_][A-Za-z0-9_]*`，大小寫有別。Runtime 依欄位用途決定取值順序。

| 欄位用途 | 設定範例 | 取值規則 |
|---|---|---|
| 一般執行參數 | `top_k: "{{TOP_K}}"` | 使用本 Pipeline 經驗證的 Request `parameters.TOP_K`，含宣告的預設值。缺值時才用 `config.secret.TOP_K`。 |
| 認證值 | `auth.bearer_token: "{{PARSER_API_TOKEN}}"` | 只從 `config.secret.PARSER_API_TOKEN` 取得。Request 中的同名參數無法改變認證值。 |
| 啟用時即須確定的值 | 用環境變數提供切分長度，例如 `max_tokens: "{{CHUNK_MAX_TOKENS}}"` | 在 System 啟用時使用 `config.secret` 的值驗證並編譯。 |

一般欄位用 Key 是否存在判斷缺值。`0`、`false`、`""` 都是已提供的值，依欄位型別和限制驗證。型別錯誤回報驗證失敗。Config 驗證時先確認來源已宣告，執行時仍無值則回報該 Key 與欄位位置。

一般參數支援整個欄位取值和一次解析。Request 值保留原型別。System 值原為文字，字串欄位原樣保留，目標明確為數字、整數、布林、陣列或物件時先以 JSON 解析再驗證。Remote 業務參數使用未指定型別的 System 值時保留字串。Import 的 `structdata`、Indexing 的 `structdata_overrides` 及 Remote 的 `output` 依原有 Schema 直接宣告。Query Rewrite 的 `prompt` 和 Embedding 文字組合依各自的模板規則。見 [Engine 模組說明](03_engine_and_components.md#src-04-51-query-transformation)。

<a id="system-secret"></a>
## System Secret

Builder 在 **其他設定 → Secret** 提供 System 共用的 Key／Value 編輯區。Key 遵守共用引用的名稱格式，且在同一 System 內唯一。Value 是環境提供的文字，可用於憑證或一般環境設定。

DEV 驗證與啟用使用 Builder 在同一個 System 填寫的字串。實際值在受保護的測試設定保存，Builder 組出有效設定給 Runtime。匯出的 Config 在同一個 `config.secret` 保留全部 Key，值一律為 `null`。正式 Runtime 啟動時用這些 Key 讀取同名環境變數，缺少任一 Key 時在就緒前回報 Key 與設定路徑。未宣告的 Key、語法錯誤、啟用所需的值缺失或型別不符，應阻擋啟用並回報欄位位置。

憑證值由 Module 的連線或認證欄位使用。例如 Remote 節點填 `auth.bearer_token: "{{PARSER_API_TOKEN}}"`，Adapter 把實際值放到 `Authorization` Header。業務 Request、Document、Queue、公開驗證結果與 Log 均不承載 Secret 明文。部署方式與成對範例見 [Runtime 啟動與 Secret 注入](06_runtime_api_and_deployment.md#system-secret-deployment)。

## Admin 全域模板

Admin 以版本化設定檔維護全域模板。目錄提供模板 ID、版本、名稱及可套用的邏輯設定。模板可示範內建方法或整組 Remote 設定。對外連線及 Secret 由套用的 System 依環境補齊。Builder 提供唯讀目錄與「選用模板」，把所選版本複製至目前草稿。User 檢查、編輯、驗證及儲存後生效；Admin 更新模板時，既有 System 持續使用已套用的設定。

## 變更影響

- Import／Parsing／Chunking、文件 Embedding 或 Indexing 若改變已索引的內容、向量或搜尋能力，依 [Runtime 索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle) 判定相容性。不相容的明確更新會刪除舊索引及資料並建立新索引。Builder 用保存的原始資料重新匯入。
- 純查詢參數變更（例如 `top_n`）、不改變輸出語意的執行調整（例如 Embedding batch size），可沿用相容索引。Inference 改用新的搜尋路徑時，仍須確認索引提供其要求的欄位和向量 Profile。
- 外部 Retrieval 使用自身資料，驗證服務契約、回傳候選及後段相依。
- 環境 Endpoint／Secret 更新後重新做連線與相容驗證。修改未啟用的內建草稿不改執行計畫。

範例見 [Remote API fixtures](../examples/user_remote_api/README.md)，舊 D-66／D-67 的候選稿見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。
