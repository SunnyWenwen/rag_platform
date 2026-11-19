# 內建方法描述與有效 Schema 推導

平台維護內建方法的描述與實作。描述保存 Module、方法版本、Config Schema、固定 I/O、可衍生欄位、資源需求及 UI 提示。Builder 用它產生表單、列出有效選項及說明欄位失效原因。Engine 用同一規則編譯有效設定。User 的 Remote API 從 System Config 取得範圍及輸出宣告，由平台產生邊界契約。

內建 Component Descriptor 必須宣告 `component_id` 和 `component_version`。Registry 以 Module、ID 和版本共同定位一份描述。Builder 發布時在 System Config 固定所選版本。平台保留 `remote_api` 給共用 Adapter，遠端服務的連線與輸出宣告由 System Config 及部署綁定提供。

<a id="descriptor-fields"></a>
## Component Descriptor 頂層欄位

下表對應 [Component Descriptor Meta-schema](../schemas/component_descriptor.draft.schema.json) 的全部頂層欄位。Catalog 的 `descriptors[]` 每筆都是一份 Descriptor。Builder 依 Descriptor 編輯該節點的 `parameters`，發布時將所選 Component 的 ID、版本與設定保存到 [System Config](05_system_config.md)。

| 欄位 | 必填 | 用途與讀取者 |
|---|---|---|
| `descriptor_version` | 是 | Builder 與 Engine 用它辨識 Descriptor 格式。現行值為 `0.2-draft`。 |
| `module` | 是 | 指定 Component 所屬的 Pipeline 模組，例如 `chunking`。Builder 據此列出可選方法，Engine 據此核對模組與 I/O。 |
| `component_id` | 是 | 指定該模組內的執行方法，例如 Chunking 的 `recursive`。Builder 保存選值，Engine 以其查找實作。 |
| `component_version` | 是 | 固定所選 Component 的版本，例如 `1.0.0`。Builder 保存版本，Engine 以 `(module, component_id, component_version)` 取得對應規格與實作。 |
| `parameters_schema` | 是 | 定義該節點 `parameters` 的 JSON Schema，包括型別、必填、預設及固定選項等。Builder 用它生成表單及檢查草稿，Engine 用它驗證設定。 |
| `io` | 是 | 宣告模組的 `input` 和 `output` 資料類型，例如 Chunking 的 `Document[]` → `Document[]`。Builder 用於預覽，Engine 核對模組邊界。檔案 Parser 也可宣告 `content_media_types`。 |
| `option_sources` | 否 | 將參數路徑對應到動態候選來源。Builder 用於下拉選單，Engine 用於檢查已選的欄位或資源引用。例如 `/profile` 從 Catalog 的 `resources.profiles` 取選項。見 [候選來源與解析方式](06_runtime_api_and_deployment.md#在-builder-解析-option_sources)。 |
| `data_rules` | 否 | 描述目前設定如何影響輸出欄位與向量。Builder 用於有效 I/O 預覽及下游欄位選項，Engine 用於編譯有效 Schema。見 [資料推導規則](#descriptor-data-rules)。 |
| `ui_hints` | 否 | Builder Renderer 用於欄位順序、分組、進階區、可見條件、專用控制項及預覽。見 [Renderer 契約](07_builder_ui.md#ui-hints-contract)。 |
| `constraints` | 否 | Builder 與 Engine 用於檢查同一 Component 內的參數關係，例如 Chunking 的 overlap 必須小於切分長度。見 [參數關聯驗證](#descriptor-constraints)。 |

`option_sources` 的鍵從該 Component 的 `parameters` 起算。路徑 `/mappings/*/source_field` 對每筆映射的來源欄位套用同一條候選規則。規則中的 `source` 指定候選集合，例如 `input.structdata`。欄位型別與必填性可分別用 `types`、`required` 篩選。

## Schema 推導

1. 從 Import 設定取得原始 `Document.structdata` 欄位，使用 [Data Meta Schema](02_data_contracts.md#data-meta-schema) 的型別與屬性。
2. 依有效方法推導該步輸出。內建方法按規則繼承或衍生欄位。Remote Parsing／Chunking 列出實際輸出，保留欄位由 Builder 帶入上游定義，轉型、補值保證及新欄位由產生階段宣告。涵蓋 Embedding 時一併宣告向量名稱、來源、維度及 Profile。
3. 將有效輸出用於下游的欄位選項、必填性、型別與相依驗證。Indexing 只合併搜尋能力覆寫，再以同一份最終設定推導候選 Schema 及 IndexBinding。選到不存在、型別不符或未保證出現的欄位時保留草稿選值並顯示錯誤。
4. 用同一有效 Schema 產生 Remote Request／Response 預覽和 Runtime 驗證。Inference 共用 QueryContext[]，候選 Document 引用 System 可檢索 Schema。

Builder 在草稿變更時推導有效 I/O 供欄位選項和預覽。W1 內建 Parser 在檔案來源模式沿用原有 structdata 並產生必填的 `contenttext`，Indexing 則以逐欄覆寫合併全文及 Filter 旗標。這兩條是 Builder 與 Engine 共用的內建推導規則。執行時，Runtime 用同一契約驗證資料及發布設定。

例：Chunking 保留 text 與 title，Embedding 可選兩者作字串來源。若 Chunking 改名為 body，原 text 映射顯示失效。若 Remote 含 Embedding 並宣告 vectors.body，Indexing 選用 vectors.body，內建向量 Retrieval 再取得對應 Profile 的 Query Encoder。

<a id="descriptor-data-rules"></a>
### `data_rules` 資料推導規則

每條規則用 `op` 指定如何從元件設定與輸入 Schema 得出輸出欄位。輸出 Schema 用於編輯和發布驗證，實際文字與向量由元件在執行時產生。

| `op` | 規則欄位 | 推導結果 |
|---|---|---|
| `declare` | `target`、`schema` | 用 `target` 讀取輸出欄名，套用 `schema` 的欄位定義。例如 Chunking 由 `/output_field` 宣告一個必填字串欄位。 |
| `copy` | `source`、`target`，可加 `for_each` | 依 `source` 取上游欄名，將它的型別、必填性和搜尋旗標繼承到 `target` 指定的輸出欄名。例如逐筆處理 `copy_fields`。 |
| `vector` | `source`、`target`、`profile`，可加 `for_each` | 以 `source` 選輸入字串欄位，`target` 命名輸出向量，再用 `profile` 讀到的 ID 查 Catalog 的向量維度。 |
| `compose` | `enabled`、`target`、`template` | 啟用時，依模板引用的必填字串欄位推導一個新的必填文字欄位。Embedding 先推導此欄位，再讓各筆向量映射引用它。 |

各路徑預設從 `parameters` 起算。`for_each` 從根層選定一個陣列，`source` 和 `target` 改從當前項目取值。`vector` 規則的 `profile` 仍從 `parameters` 根層取值，各項共用同一 Profile。

例如 Embedding 的 Catalog 規則為：

```json
{
  "op": "vector",
  "for_each": "/mappings",
  "source": "/source_field",
  "target": "/vector_name",
  "profile": "/profile"
}
```

當 `parameters.mappings[0]` 是 `{"source_field": "text", "vector_name": "body_vec"}` 且 `parameters.profile` 為 `"text-v1"`，規則就會從當前列讀到 `text` 與 `body_vec`，再從根層讀到 `text-v1`。有效輸出因此包含由 `structdata.text` 產生的 `vectors.body_vec`，其維度來自 Catalog 的 `resources.profiles["text-v1"]`。

其他實例見 [Recursive Chunking Descriptor](../examples/system_config/recursive.descriptor.json) 與 [Runtime Catalog 回應](../examples/system_config/runtime_catalog.response.json)。

<a id="descriptor-constraints"></a>
## `constraints` 參數關聯驗證

現行支援 `lt`。它從 `parameters` 讀取 `left`、`right` 指定的數值，要求左值嚴格小於右值。例如 `{"op": "lt", "left": "/overlap_tokens", "right": "/max_tokens"}` 在兩者相等時也會驗證失敗。這項規則由 Builder 在編輯時檢查，Engine 在發布驗證時再次檢查。

## Builder 表單與契約預覽

[Builder 表單 Descriptors](../examples/system_config/builder_form.descriptors.json) 同時提供參數 Schema、選項來源、資料推導規則及表單提示。單檔 Prototype 內嵌同一份 Catalog，離線測試驗證兩份內容一致。

| Descriptor 欄位 | Builder 行為 |
|---|---|
| `io.input`／`io.output` | 指定 I/O 的資料類型。Builder 以目前草稿的欄位和上游宣告顯示每個模組的有效輸入／輸出。Remote 跨模組範圍顯示整段邊界。 |
| `io.content_media_types` | 內建檔案 Parser 宣告接受的 MIME types。Import 的 `source: content` 開放這些 Parser，並對 Ingestion 的 `content.media_type` 套用所選 Parser 的限制。 |
| `ui_hints.previews` | `effective_io` 預設收合。Import 的 `ingestion_request` 同樣預設收合，顯示入口 JSON Schema 和對應 Request 範例。 |
| `ui_hints.order`／`groups`／`advanced` | 以 JSON Pointer 指定欄位順序、分組及進階區。分組可提供 `example`。Embedding 的組合文字分組置於表單上方，服務來源與 Profile 同屬模型設定分組，向量映射以可新增的單一清單呈現。 |
| `ui_hints.controls` | 以相對於 `parameters` 的 JSON Pointer 宣告專用控制項。支援 `structdata_editor`、`structdata_overrides_editor`、`vector_checklist` 及 `textarea`。各 hint 的格式、預設、輸入資料及呈現見 [Builder Renderer 契約](07_builder_ui.md#ui-hints-contract)。 |
| `ui_hints.fixed_filters` | Inference Input 以 `advanced` 將固定 Filter 放在預設收合的進階設定。值儲存於 `pipelines.inference.fixed_filters`。 |
| `ui_hints.visible_when` | 依同一 Component 的其他草稿值判斷欄位可見性。例如啟用組合文字才顯示模板，選兩條搜尋路徑才顯示融合策略。 |
| `parameters_schema.properties.*.default` | 提供預設值。Embedding、Elasticsearch、Local Search 的 MongoDB 和 Rerank 服務來源預設 `DEV test use`。 |

例如 Import 的 `parameters_schema.properties.structdata.$ref` 指向 Data Meta Schema 以約束參數形狀，`ui_hints.controls["/structdata"] = "structdata_editor"` 指定欄位表。Indexing 的 `structdata_overrides_editor` 必須對應 Data Meta Schema 的 `#/$defs/overrides`。註冊時檢查控制項、參數路徑與形狀相容性。

Dense Embedding 使用一份 `mappings[]` 清單，每筆有 `source_field` 和 `vector_name`。清單至少一筆，預設 `text → text`。讀取舊版 Config 時，原本頂層的映射會轉成清單第一筆。啟用文字組合時，先依 `composition_template` 產生 `composition_field`。模板引用 `{{structdata.欄位}}`，來源須為現有且必填的字串，輸出欄位名稱須唯一。每筆映射都可選該衍生欄位，所有映射共用 Embedding Profile。

`profile` 識別向量空間及模型／版本、維度、文件與查詢的編碼設定。Query Encoder 須與文件向量相容。同時選用多個向量欄位時，每路檢索依其索引綁定的 Profile 進行。

<a id="component-parameter-scope"></a>
### 內建服務參數的適用範圍

| 參數 | 現行契約 |
|---|---|
| Chunking 的 `tokenizer_profile_id` | 取自 Catalog 的 `resources.tokenizer_profiles`。切分方式及參數見 [Engine Chunking](03_engine_and_components.md#chunking)。 |
| Embedding 的 `profile` | 取自 Catalog 的 `resources.profiles`，來源欄位與向量名稱寫在 `mappings[]`。W1 HTTP 範例以這份 Profile 的維度為準。 |
| Elasticsearch 的 `service_ref` | W1 以 Catalog 的 `resources.elasticsearch_services` 解析此邏輯引用。主機及認證資料屬環境綁定。 |
| Local Search 的 `persistence` | `memory` 或 `mongodb`，隨有效 Config 跨環境沿用。MongoDB 的綁定及恢復見 [Q-012](08_plan_and_decisions.md#q-012) 與 [Q-021](08_plan_and_decisions.md#q-021)。 |
| Rerank 的 `text_field`、`query_source` | `text_field` 存候選 `structdata` 的裸欄名，例如 `text`。`query_source` 選原始問題或當前 Query，評分邊界見 [Engine Rerank](03_engine_and_components.md#src-04-53-rerank)。 |

Descriptor 另有 `service_source` 及自行提供服務的編輯欄位，例如 `embedding_service_ref`、`embedding_model`、`dimensions`、`elasticsearch_service_ref`、`mongo_service_ref`、`rerank_service_ref`。這些欄位可供表單開發。發布時如何映射至正式服務綁定，以及自訂 Embedding 設定如何與 `profile` 一致，依 [Q-003](08_plan_and_decisions.md#q-003)、[Q-021](08_plan_and_decisions.md#q-021) 確認。W1 的發布與匯入 Mock 採 Catalog 已註冊的資源。

Indexing 的 `vector_fields` 接受要建立索引的具名向量清單。既有的單欄 `vector_name` 仍可讀取，同一有效設定只採其中一種表示。W1 Prototype 的發布模擬使用單欄格式。Embedding 產生多個向量後，Builder 可選擇要讓 Retrieval 搜尋的欄位。

內建 Retrieval 的 `vector_fields` 和 `fulltext_fields` 都可多選，選項分別來自 `index_plan.vectors` 和 `index_plan.fulltext`。至少選一個欄位。每個向量路徑的查詢 Profile 由對應的 IndexBinding 推導。兩組欄位下方依序顯示每路 Top K、多路時的融合策略、Group by 合併欄位和 Top N。

<a id="prototype-component-inventory"></a>
### Prototype Component 清冊

[完整表單 Descriptor 清單](../examples/system_config/builder_form.descriptors.json)涵蓋 9 個 Module 的 20 個內建 Component。以下「本次補齊」指加入完整表單清單。W1 Prototype 的執行模擬仍以既有 9 個元件組合驗收，其他表單可編輯並保存草稿。

| Module | 內建 Component ID | 表單規則與盤點結果 |
|---|---|---|
| Import | `platform` | 文件欄位表、Request 參數進階區、匯入契約預覽。既有 hints 涵蓋。 |
| Parsing | `passthrough`、`pdf`、`pdf_ocr`、`office`、`image_ocr`、`text`、`json` | 本次補齊 `passthrough`。檔案方法依 `io.content_media_types` 與 Import 入口形式決定可選性，Parser 參數沿用通用欄位。 |
| Chunking | `recursive`、`fixed_size`、`header_aware` | 本次補齊三份完整表單。切分及複製來源依上游欄位，Tokenizer 由 Catalog 提供。分隔符、標題層級及保留原文沿用列表、布林及進階區。 |
| Embedding | `dense` | 既有群組、模板文字欄、映射陣列保留。服務選擇和組合文字的欄位開關採 `visible_when`。 |
| Indexing | `elasticsearch`、`local` | 既有欄位覆寫表和向量清單保留。Elasticsearch／MongoDB 的連線相關欄位採 `visible_when`。 |
| Inference Input | `platform` | 既有 Request 參數進階區和 `fixed_filters`。 |
| Query Transformation | `none`、`rewrite` | 本次補齊兩份表單。Rewrite Prompt 沿用 `textarea`，有多條 Query 時依 `visible_when` 顯示跨 Query 規則。跨 Query 設定的正式位置見 [System Config](05_system_config.md#inference-result-processing)。 |
| Retrieval | `builtin` | 既有全文／向量選項、Group by 和 Top N。多路與 RRF 專屬設定採 `visible_when`。 |
| Rerank | `none`、`model_api` | 本次補齊 `none`。Rerank 服務來源的自訂連線欄位採 `visible_when`。 |

Parsing、Chunking、Embedding、Query Transformation、Retrieval、Rerank 另可選用共用 `remote_api` Adapter。這六個入口使用 [System Config 的 Remote 節點契約](../schemas/system_config.draft.schema.json)渲染範圍、服務引用、連線及輸出宣告。Adapter 以選定區段的 I/O 邊界推導契約。所需新增 hint 為 `visible_when`，上游選項沿用 `option_sources`。

<a id="group-by-option-source"></a>
## 分組欄位的選項來源

Retrieval／Rerank 的 Descriptor 可用 `parameters_schema` 表達 `group_by` 為非空且不重複的欄位陣列，以 `/group_by/*` 檢查每個欄位。跨 Query 設定沿用同一份參數形狀及欄位來源。Builder 開啟分組時預選 `document_id`。

Meta-schema 的來源 `candidate.document_fields` 由 System 的有效候選 Document Schema 取得 `document_id` 與 `structdata` 欄位。`group_by` 選項限制為 `string`。候選欄位可以選填，執行時缺值的候選獨立保留。

```yaml
parameters_schema:
  type: object
  properties:
    group_by:
      type: array
      minItems: 1
      uniqueItems: true
      items:
        type: string
        minLength: 1
option_sources:
  "/group_by/*":
    source: candidate.document_fields
    types: [string]
```

離線範例驗證內建 Retrieval 的分組欄位選項，正式 Runtime 及跨 Query 設定整合依里程碑驗收。

## 內建描述保留的能力

| 能力 | 例子 |
|---|---|
| 固定欄位 | 內建 Parser 輸出 contenttext |
| 上游繼承 | metadata、文件識別及未改寫的資料欄位 |
| 由 Config 宣告欄位 | Chunking 的輸出與複製欄位 |
| 欄位映射 | structdata.text → vectors.text |
| 動態選項 | 由上游的必填字串提供 Embedding 來源 |
| 條件與相依 | 向量維度／Profile 一致、失效來源提示、有效設定排除未選分支 |

平台內部的 Descriptor Meta-schema、規則鍵名、版本包裝與 UI Renderer 仍依 [開發計畫](08_plan_and_decisions.md#q-002)收斂。既有 D-67 細化及 DS-01～DS-13 的候選格式供平台內部設計查考。舊 Developer 交付及 Manifest 推導範例見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。

## Remote 與模板的來源

System Config 保存 User 的區段選擇、參數引用及實際輸出欄位宣告。Descriptor 的參數 Schema 描述解析後的型別與限制，Runtime 依[共用取值規則](05_system_config.md#parameter-references)解析 `{{KEYNAME}}`，再驗證目標參數。見 [System Secret](05_system_config.md#system-secret)。模板帶入這些設定的可編輯副本。User 或 AI 助手修改後重新推導與驗證。Remote I/O、參數與錯誤語意見 [Engine](03_engine_and_components.md#remote-api)，環境連線及認證見 [Runtime](06_runtime_api_and_deployment.md#remote-service-deployment)。
