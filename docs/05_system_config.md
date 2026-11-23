# System Config、模板與版本

## 草稿、有效設定與部署

Workspace 管理多個 System。System ID、Config Revision、source_revision、索引版本、Runtime Image 版本各自獨立。Builder 草稿可保存未啟用方法；編譯只使用所選方法與 Remote 涵蓋區段，拒絕範圍重疊。切回內建方法時恢復原草稿設定。

同一 Config Revision 在 DEV／FTEST／ENT 沿用相同邏輯設定。端點、Secret 的實際值、DB／索引實體目標及 Runtime 限制屬環境綁定。變更方法、模型語意、維度或資料欄位產生新 Revision，依相依範圍判斷重建。每次請求採單一有效設定快照；有 queued／running Ingestion 時可存草稿，等該 System 工作完成再啟用新版。

[System Config Schema 草案](../schemas/system_config.draft.schema.json)驗證發布快照。首版 DEV／FTEST／ENT 使用受管 Elasticsearch，連線依 [Elasticsearch 服務來源](#elasticsearch-service-source) 與目標環境解析。可參照 [ES 發布請求](../examples/system_config/README.md#runtime-http-examples)及[內建／Remote Parsing 的離線對照](../examples/system_config/README.md#local-search-config-examples)。

DEV 由 Builder 下發 System Config，獨立部署則由 Runtime 啟動時讀取指定版本。Runtime 本身的預設值與環境覆寫另由部署管理。見 [設定來源與保存位置](06_runtime_api_and_deployment.md#runtime-config-sources)。

同一份發布快照包含 Ingestion 與 Inference。`pipeline` 是生命週期請求或環境部署設定的選擇欄位，位於 `config` 之外。獨立啟用其中一條流程時，沿用同一 System 的發布版本及索引綁定。[流程部署契約](06_runtime_api_and_deployment.md#runtime-pipeline-deployment)

每個有效節點以 `component_id` 選擇執行方式，並以 `component_version` 固定元件版本。內建元件使用該版本的 Descriptor 驗證參數。Remote API 共用平台保留的 `component_id: remote_api`，服務網址、認證及服務版本直接設定在該節點，見 [Remote 節點設定](#remote-node-settings)。Builder 設計可用同一個「執行方式」欄位選 Recursive、Fixed-size 或 Remote API。

<a id="config-fields"></a>
### Config 快照與節點欄位

| 路徑 | 責任與語意 |
|---|---|
| `system_id` | Builder 建立時配發的穩定 UUID，匯出及跨環境部署沿用。HTTP 驗證和套用時由路徑提供。[部署環境與索引歸屬](06_runtime_api_and_deployment.md#runtime-index-ownership) |
| `config_revision` | Builder 指派的發布版本。新版本在套用請求傳入，草稿驗證使用自己的 `draft_revision`。 |
| `config` | 有效邏輯設定。Runtime 驗證與套用請求直接帶這個內層物件。 |
| `config.contract_version` | 此 Config 的格式版本，現行為 `0.2-draft`。 |
| `config.secret` | 選填的 System 級敏感值 KV。見 [Variable 與 Secret](#system-secret)。 |
| `config.variable` | 選填的 System 級一般環境參數 KV，例如租戶 ID、區域代碼或 Remote 服務網址。見 [Variable 與 Secret](#system-secret)。 |
| `config.pipelines` | 包含 `ingestion`、`inference`。每個有效模組對應一個節點。 |
| `config.pipelines.inference.mcp` | 選填的 [MCP 查詢工具](06_runtime_api_and_deployment.md#inference-mcp)設定：`tool_name`（預設 `search`）、`description` 及文字呈現使用的 `text_field`（預設 `text`，須為有效 `structdata` 字串欄位）。不參與索引指紋。 |
| 節點的 `component_id`、`component_version`、`parameters` | 分別選方法、固定版本、保存該方法的設定。個別參數由所選 Descriptor 的 `parameters_schema` 定義。 |
| Remote 節點的 `contract_version`、`through`、`connection`、`auth`、`revision`、`runtime_only_parameters`、`output` | `contract_version` 固定此節點使用的 [Remote HTTP 版本](03_engine_and_components.md#remote-api)，與 `component_version` 各自保存。`through` 含括區段最後一個模組，首節點由 Pipeline 上的 key 指定。`connection` 保存服務網址的 Variable 引用、逾時與自訂 Header。選填的 `auth.bearer_token` 使用 Secret 的 `{{KEY}}`。Ingestion Remote 必填 `revision`，並以 `output` 宣告適用的 `structdata` 或 `vectors`；Inference 依 System 的有效候選 Schema 驗證。欄位規則見 [Remote 節點設定](#remote-node-settings)。 |

新增 Remote 節點時，Builder 填入目前可用的契約版本。發布及匯出沿用已保存的版本。發布時依固定的 Pipeline 順序核對節點。Remote 區段涵蓋的後續節點在有效設定中省略，由首節點涵蓋。JSON Schema 驗證結構，編譯器檢查覆蓋是否完整且無重疊、元件版本、欄位相依及引用。見 [Runtime 驗證契約](06_runtime_api_and_deployment.md#config-validation-api)。

<a id="remote-node-settings"></a>
### Remote 節點設定

使用者在 Pipeline 節點把執行方式切成 Remote API 後，直接在同一個節點設定外部服務。每個 Remote 節點各自保存連線，多個節點呼叫同一服務時分別設定。以下是涵蓋 Parsing 的 Ingestion 節點。

```json
"parsing": {
  "component_id": "remote_api",
  "component_version": "1.0.0",
  "contract_version": "1",
  "through": "parsing",
  "connection": {
    "url": "{{REMOTE_PARSING_URL}}",
    "timeout_seconds": 30,
    "headers": {"X-Tenant": "{{REMOTE_PARSING_HEADER_X_TENANT}}"}
  },
  "auth": {"bearer_token": "{{REMOTE_PARSING_TOKEN}}"},
  "revision": "2026.11.1",
  "parameters": {"language": "zh-TW", "trace_label": "{{trace_label}}"},
  "runtime_only_parameters": ["trace_label"],
  "output": {"structdata": {"body": {"type": "string", "required": true}}}
}
```

| 欄位 | Builder 畫面 | 規則 |
|---|---|---|
| `through` | 基本：替換範圍 | 依 [可替換範圍](03_engine_and_components.md#remote-api)選擇連續區段。 |
| `connection.url` | 基本：服務網址 | Builder 依節點自動建立 Variable `REMOTE_<MODULE>_URL`，使用者在節點上輸入 DEV 值。Config 一律保存完整 `{{KEY}}` 引用，不保存網址字面值。啟動解析後須是絕對 `http` 或 `https` URL。 |
| `auth.bearer_token` | 基本：認證方式「無」或「Bearer Token」 | 選 Bearer Token 時，Builder 自動建立 Secret `REMOTE_<MODULE>_TOKEN`，畫面以遮罩輸入 DEV 值。只能引用 Secret。 |
| `revision` | 基本：服務版本 | Ingestion 必填，Inference 選填。固定字串，不能使用 `{{KEY}}`。服務處理邏輯改變時由使用者更新，Ingestion 的新值會觸發索引重建。畫面提示「處理邏輯改變時請更新，會觸發索引重建」。 |
| `parameters` | 基本：業務參數表 | 由服務方定義的業務參數。取值規則見 [共用引用語法](#parameter-references)。 |
| `runtime_only_parameters` | 基本：業務參數表的「僅執行期使用」勾選 | 只用於 Remote Ingestion，列出不影響索引輸出的頂層參數名稱。 |
| `output` | 基本：輸出宣告 | 只用於 Remote Ingestion。涵蓋 Parsing／Chunking 時宣告 `structdata`，涵蓋 Embedding 時另列向量表。 |
| `connection.timeout_seconds` | 進階：逾時秒數 | 正整數，預設 30。不得超過該流程的執行期限：Ingestion 單文件 600 秒，Query 60 秒。 |
| `connection.headers` | 進階：自訂 Header | 值為字面字串，或勾選「依環境不同」後由 Builder 建立 Variable `REMOTE_<MODULE>_HEADER_<NAME>` 並保存引用。不可引用 Secret，也不可覆寫 `Authorization`、`Content-Type`、`Content-Length`、`Host`、`X-Request-Id`。名稱比對不分大小寫。 |
| `contract_version` | 進階：契約版本（唯讀） | 新增節點時填入目前支援的版本。進階區另提供契約預覽與回應驗證。 |

`<MODULE>` 為節點的模組鍵轉大寫，`<NAME>` 為 Header 名稱轉大寫並把 `-` 換成 `_`，例如 `REMOTE_PARSING_HEADER_X_TENANT`。這些 Key 顯示在 [其他設定](#system-secret) 的 Variable／Secret 表，標示「由 Remote 節點管理」。使用者可在表中修改值，但不能改名或刪除。移除 Remote 節點或關閉對應設定時，Builder 一併移除這些 Key。自動 Key 與既有 Key 衝突時，Builder 加上未占用的數字後綴。

Remote Ingestion 的 [索引指紋](06_runtime_api_and_deployment.md#index-fingerprint-v1-proposal)包含 `through`、`contract_version`、`revision`（投影為 `implementation_revision`）、排除僅執行期參數後的 `parameters` 及 `output`。`connection` 與 `auth` 屬環境綁定，不參與指紋。換網址、Header、逾時或 Token 時，Runtime 重新連線，不重建索引。

匯出時 `connection.url` 與 Variable 型 Header 的 Key 保留在 `config.variable`，Token 保留在 `config.secret`，值都設為 `null`，部署方分別以 ConfigMap 與 Kubernetes Secret 供值。匯出畫面列出這些 Key。Embedding、LLM 與 Rerank 等模型服務是否改由平台統一提供另行討論，不影響 Remote 節點的欄位。

<a id="config-enums"></a>
### 固定選項的儲存值

內建 Component 透過 `parameters_schema` 的 `$ref` 引用 [Config 列舉 Schema](../schemas/config_enums.schema.json)。Config 保存 Schema 定義的代碼，Builder 將代碼對應到畫面標籤。Runtime 依目標 Component Descriptor 驗證實際值。

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
| 其他設定 → Variable／Secret | 管理同一 System 各 Module 可引用的 KV；輸入 DEV 測試值。Remote 節點自動建立的 Key 也列在此處。 |
| Remote API | 在選用 Remote 的節點設定替換範圍、服務網址、認證、服務版本、業務參數、Ingestion 輸出欄位及向量宣告。見 [Remote 節點設定](#remote-node-settings)。 |

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

Retrieval 與 Rerank 各自在 Component `parameters` 設定當步分組與 Top N。跨 Query 合併由 Query Transformation 配置。內建 `rewrite` 的發布欄位位於 `config.pipelines.inference.query_transformation.parameters`，沿用 [Rewrite Descriptor](../examples/system_config/rewrite.descriptor.json) 的欄位和值。

| 設定 | 內容 |
|---|---|
| Retrieval 參數 | `fulltext_fields`、`vector_fields`、`per_route_k`、多路時必填的同 Query 融合策略、可選 `group_by` 和 `top_n` |
| Rerank 參數 | 評分服務、內容欄位、提問來源、`group_by`、Rerank Top N |
| 跨 Query 合併時點 | `cross_query_at` 選擇在 Retrieval 完成時合併，或先逐 Query Rerank 再合併。合法值與預設見 [Config 列舉 Schema](../schemas/config_enums.schema.json)。 |
| 跨 Query 分組與截斷 | 選填 `cross_query_group_by` 和 `cross_query_top_n`。 |

內建 Retrieval 的全文與向量欄位皆可多選，每個向量欄位依 IndexBinding 的 `embedding_profile_id` 決定 Query Encoder。`per_route_k` 是每個 Query 在個別路徑的搜尋上限。多路時必選 RRF 或 Sum Score，交付時每個 Query 只有一份清單。Adapter 負責執行選定的策略。策略的專屬參數與預設值留待定義。全文和 Filter 選項依 [欄位總表及 Filter 契約](02_data_contracts.md#data-meta-schema) 推導。

`group_by` 可選 `document_id` 或一個以上有效的 `structdata` 字串欄位，也可以組合使用。選多欄時以欄位值組合作為分組鍵；未設定分組時沿用排序後的清單。當步分組在排序後、當步 Top N 前執行。跨 Query 依 `data_id` 取最高分、可選分組及跨 Query Top N 的順序，見 [Engine 結果處理](03_engine_and_components.md#cross-query-merge)。

Builder 依 `count + (include_original ? 1 : 0)` 決定是否顯示跨 Query 設定。Engine 依進入平台結果處理的有效 Query 數執行，達兩個即合併。省略時點時使用 Schema 預設。單 Query 略過跨 Query 合併；表單切回多 Query 時可恢復草稿中的原設定。

以下是 `config.pipelines.inference` 的 Query Transformation 節點片段。它產生兩個改寫 Query 並保留原始 Query，三份清單逐 Query Rerank 後取最高分代表，再依文件分組並取前五筆。

```yaml
query_transformation:
  component_id: rewrite
  component_version: "1.0.0"
  parameters:
    llm_ref: default-llm
    prompt: "為 {{query}} 產生 {{count}} 個查詢。"
    count: 2
    include_original: true
    cross_query_at: after_rerank
    cross_query_group_by: [document_id]
    cross_query_top_n: 5
```

W1 HTTP 範例採單 Query，多 Query 合併留在 M2 驗收。Remote 區段涵蓋結果處理時，由外部服務負責該區段的處理。Remote 只產生多 Query 並交由平台合併時，平台設定如何存於 Query Transformation 節點，需依 [Q-014](08_plan_and_decisions.md#q-014)／[Q-028](08_plan_and_decisions.md#q-028) 定義，Remote 的 `parameters` 仍承載外部服務自身的參數。

## 執行參數

Import／Inference Input 各自宣告名稱、型別、必填與預設值。Import 的值放在整批 Ingestion Request 的 `parameters`，Inference 的值放在該次查詢的 `parameters`。執行參數留在呼叫環境，與 Document、metadata、索引內容分開。

現行表單在 `import.parameters.request_parameters` 或 `inference_input.parameters.request_parameters` 宣告。每列包含 `name`、`type`、`required` 及選填的 `default_value`。可選型別見 [Config 列舉 Schema](../schemas/config_enums.schema.json) 的 `request_parameter_type`。`default_value` 存 JSON 文字，例如 `{"default_value":"\"zh-TW\""}`。Runtime 驗證已宣告的 Request 參數、套用宣告的預設值，並拒絕缺少必填項目或型別不符的請求。

<a id="parameter-references"></a>
### 共用引用語法

Builder 在支援引用的欄位統一填 `{{KEYNAME}}`。引用名稱採 `[A-Za-z_][A-Za-z0-9_]*`，大小寫有別。Runtime 依欄位用途決定取值順序。

| 欄位用途 | 設定範例 | 取值規則 |
|---|---|---|
| 一般執行參數 | `top_k: "{{TOP_K}}"` | 先取當前 Pipeline 已驗證的 Request 參數（含宣告預設值），再取 `config.variable.TOP_K`。 |
| 認證與連線值 | `auth.bearer_token: "{{REMOTE_PARSING_TOKEN}}"`、PLED ES 的 `es_number`、`account`、`password` | 引用從同一 System 的 `config.secret` 取得。PLED 匯出採下方的連線規則。 |
| Remote 連線 | `connection.url: "{{REMOTE_PARSING_URL}}"`、Variable 型 Header | 只從 `config.variable` 取值，不讀 Request 參數。 |
| 影響索引的設定 | `max_tokens: 500` | 固定於 Config Revision。發布時遇到 `{{KEY}}` 回 `422 CONFIG_VALIDATION_FAILED` 並定位欄位。 |

一般欄位用 Key 是否存在判斷缺值。`0`、`false`、`""` 都是已提供的值，依欄位型別和限制驗證。型別錯誤回報驗證失敗。Config 驗證時先確認來源已宣告，執行時仍無值則回報該 Key 與欄位位置。

一般參數支援整個欄位取值及一次解析。Request 值保留原型別，Variable 按目標型別解析。內建 Ingestion 的入庫設定、Import 的 `structdata`、Indexing 的索引設定與覆寫，以及 Remote 的 `revision`、`output` 使用固定值。Import 宣告的 Request 參數可供執行期欄位取用。Embedding 可沿用 `{{structdata.title}}` 等資料欄位模板，Rewrite 保留 `{{query}}`、`{{count}}` 內建模板變數。

Remote Ingestion 預設將業務參數視為會影響索引。服務提供者確認某個頂層參數只供執行期使用時，在該節點的 `runtime_only_parameters` 列出參數名稱，例如只用於記錄的 `trace_label`。這些參數可引用 Request 或 Variable，並排除於索引指紋。其餘業務參數須固定於 Revision。會改變資料範圍、解析或向量結果的語言、租戶或策略皆按輸出影響判定。Remote Inference 的業務參數沿用一般取值規則。

<a id="system-secret"></a>
## System Variable 與 Secret

Builder 在 **其他設定** 提供獨立的 Variable 和 Secret Key／Value 表。Variable 用於跨環境不同的一般參數，例如租戶 ID、區域代碼或 Remote 服務網址；Secret 用於憑證等敏感值。兩者的 Value 皆以字串填寫。Key 遵守共用引用的名稱格式，且在同一 System 的兩張表間必須唯一，因為部署時都讀取同名環境變數。[Remote 節點](#remote-node-settings)自動建立的 Key 也列在兩張表中，由節點管理。

DEV 驗證與啟用使用 Builder 針對同一 System 填寫的值。Variable 的 DEV 值可隨草稿保存，Secret 的 DEV 值由受保護的測試設定提供。匯出保留 `config.variable` 與 `config.secret` 的 Key，值一律設為 `null`。正式 Runtime 啟動時以這些 Key 讀取同名環境變數。缺少值、未宣告的引用、型別或語法錯誤均應阻擋啟用並回報欄位位置。

Secret 只供明確列出的認證欄位使用，例如 Remote `auth.bearer_token` 與 PLED ES 的 [連線欄位](#elasticsearch-service-source)。發布時檢查一般參數、巢狀 Remote 參數、Remote 網址與 Header 及 Prompt，若在認證欄位以外引用 Secret 即回 `422 CONFIG_VALIDATION_FAILED` 並定位欄位。一般參數解析只取 Request 或 Variable。Runtime 在寫 Log、Trace 或回傳診斷前先排除認證欄位與 Header，輸出路徑再將識別到的 Secret 值遮罩為 `***`。部署注入見 [Runtime 啟動與環境注入](06_runtime_api_and_deployment.md#system-secret-deployment)。

<a id="system-api-secret-fields"></a>
### System API 認證欄位

Builder 的 Secret 區固定顯示以下欄位。Key 和帳密格式以 [System Config Schema](../schemas/system_config.draft.schema.json#/$defs/system_secret) 為準。

| 流程 | 帳號 Key | 密碼 Key |
|---|---|---|
| Ingestion | `INGESTION_API_USERNAME` | `INGESTION_API_PASSWORD` |
| Inference | `INFERENCE_API_USERNAME` | `INFERENCE_API_PASSWORD` |

Builder 建立 System 時預填 `ingestion`、`inference`，並為該 System 的兩條流程各產生可修改的獨立隨機 DEV 密碼。啟用流程時須有對應的一組有效帳密。這些 Key 由 Runtime 的 HTTP 認證層讀取，保留給入站 API，禁止以 Module 表達式引用，也不能作為 System Variable。

匯出時兩組 Key 保留，值設成 `null`。由部署方自行在目標環境供應已啟用流程的帳密。分 Pod 時各 Runtime 只需注入自己流程的帳密。認證值屬部署綁定，輪替不影響索引指紋。[呼叫路由與驗證位置](06_runtime_api_and_deployment.md#runtime-basic-authentication)

<a id="elasticsearch-service-source"></a>
## Elasticsearch 服務來源

設定位置為 `config.pipelines.ingestion.indexing.parameters`。可選來源、必填條件與值型別由 [Elasticsearch 連線 Schema](../schemas/elasticsearch_connection.schema.json) 定義。內建 Inference 沿用同一 System 的索引綁定。

| Builder 選項 | 屬性及執行行為 |
|---|---|
| Builder 測試用 ES | `service_source: dev_test`。Builder DEV 預設選項，Runtime 使用部署管理員預先綁定的 PLED 測試 ES。選取時表單只顯示服務來源。 |
| PLED ES | `service_source: pled_es`。Builder 顯示並要求 `es_number`、`account`、`password`。`es_number` 為原樣字串，可保留前導零。`account` 為登入帳號。 |

DEV 選 PLED 時，Builder 接受 ES 編號及帳號的字串值，密碼由 [System Secret](#system-secret) 保存，Config 的 `password` 採完整引用。

匯出 FTEST／ENT 時，Builder 依發布快照產生部署用 System Config。DEV 的 `dev_test` 自動改成 `pled_es`，已選 `pled_es` 的來源值維持相同。三個 PLED 欄位在匯出檔都使用 Secret 引用，對應的 `config.secret` 值設成 `null`。預設 Key 由 [連線 Schema](../schemas/elasticsearch_connection.schema.json) 提供。原欄位已有有效 Secret 引用時可沿用其 Key，新增 Key 衝突時使用未占用的後綴。Kubernetes Env 名稱須與實際匯出 Key 對應，部署者為三個值各自填寫目標環境的 Secret。

匯出保留原 `system_id`、`config_revision`、Pipeline 邏輯與索引 mapping／欄位設定。ES 來源和三個連線欄位屬 D-30 的環境綁定，在部署用 Config 序列化。Runtime 啟動時解析 Secret，依編號與帳密連線，並核對目標索引綁定。連線欄位禁止由業務請求覆寫。跨環境的 Config Hash 範圍見 [Q-015](08_plan_and_decisions.md#q-015)，接線方式見 [PLED Config 與部署範例](../examples/system_config/README.md#pled-elasticsearch-example)。

## Admin 全域模板

Admin 以版本化設定檔維護全域模板。目錄提供模板 ID、版本、名稱及可套用的邏輯設定。模板可示範內建方法或整組 Remote 設定。對外連線及 Secret 由套用的 System 依環境補齊。Builder 提供唯讀目錄與「選用模板」，把所選版本複製至目前草稿。User 檢查、編輯、驗證及儲存後生效；Admin 更新模板時，既有 System 持續使用已套用的設定。

## 變更影響

- Import／Parsing／Chunking、文件 Embedding 或 Indexing 若改變已索引的內容、向量或搜尋能力，依 [Runtime 索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle) 判定相容性。不相容的明確更新會刪除舊索引及資料並建立新索引。Builder 用保存的原始資料重新匯入。
- 純查詢參數變更（例如 `top_n`）、不改變輸出語意的執行調整（例如 Embedding batch size），可沿用相容索引。Inference 改用新的搜尋路徑時，仍須確認索引提供其要求的欄位和向量 Profile。
- 外部 Retrieval 使用自身資料，驗證服務契約、回傳候選及後段相依。
- 環境 Endpoint／Secret 更新後重新做連線與相容驗證。修改未啟用的內建草稿不改執行計畫。

範例見 [Remote API fixtures](../examples/user_remote_api/README.md)，舊 D-66／D-67 的候選稿見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。
