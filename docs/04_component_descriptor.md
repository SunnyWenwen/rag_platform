# 內建方法描述與有效 Schema 推導

平台維護內建方法的描述與實作。描述保存 Module、方法版本、Config Schema、固定 I/O、可衍生欄位、資源需求及 UI 提示。Builder 用它產生表單、列出有效選項及說明欄位失效原因。Engine 用同一規則編譯有效設定。User 的 Remote API 從 System Config 取得範圍及輸出宣告，由平台產生邊界契約。

內建 Component Descriptor 必須宣告 `component_id` 和 `component_version`。Registry 以 Module、ID 和版本共同定位一份描述。Builder 發布時在 System Config 固定所選版本。平台保留 `remote_api` 給共用 Adapter，遠端服務的連線與輸出宣告由 System Config 及部署綁定提供。

## Schema 推導

1. 從 Import 設定取得原始 `Document.structdata` 欄位，使用 [Data Meta Schema](02_data_contracts.md#data-meta-schema) 的型別與屬性。
2. 依有效方法推導該步輸出。內建方法按規則繼承或衍生欄位。Remote Parsing／Chunking 列出實際輸出，保留欄位由 Builder 帶入上游定義，轉型、補值保證及新欄位由產生階段宣告。涵蓋 Embedding 時一併宣告向量名稱、來源、維度及 Profile。
3. 將有效輸出用於下游的欄位選項、必填性、型別與相依驗證。Indexing 只合併搜尋能力覆寫，再以同一份最終設定推導候選 Schema 及 IndexBinding。選到不存在、型別不符或未保證出現的欄位時保留草稿選值並顯示錯誤。
4. 用同一有效 Schema 產生 Remote Request／Response 預覽和 Runtime 驗證。Inference 共用 QueryContext[]，候選 Document 引用 System 可檢索 Schema。

例：Chunking 保留 text 與 title，Embedding 可選兩者作字串來源。若 Chunking 改名為 body，原 text 映射顯示失效。若 Remote 含 Embedding 並宣告 vectors.body，Indexing 選用 vectors.body，內建向量 Retrieval 再取得對應 Profile 的 Query Encoder。

## Builder 表單與契約預覽

[Builder 表單 Descriptors](../examples/system_config/builder_form.descriptors.json) 同時提供參數 Schema、選項來源、資料推導規則及表單提示。單檔 Prototype 內嵌同一份 Catalog，離線測試驗證兩份內容一致。

| Descriptor 欄位 | Builder 行為 |
|---|---|
| `io.input`／`io.output` | 指定 I/O 的資料類型。Builder 以目前草稿的欄位和上游宣告顯示每個模組的有效輸入／輸出。Remote 跨模組範圍顯示整段邊界。 |
| `io.content_media_types` | 內建檔案 Parser 宣告接受的 MIME types。Import 的 `source: content` 開放這些 Parser，並對 Ingestion 的 `content.media_type` 套用所選 Parser 的限制。 |
| `ui_hints.previews` | `effective_io` 預設收合。Import 的 `ingestion_request` 同樣預設收合，顯示入口 JSON Schema 和對應 Request 範例。 |
| `ui_hints.order`／`groups`／`advanced` | 以 JSON Pointer 指定欄位順序、分組及進階區。分組可提供 `example`。Embedding 的組合文字分組置於表單上方，服務來源與 Profile 同屬模型設定分組，向量映射以可新增的單一清單呈現。 |
| `ui_hints.controls` | `/vector_fields: vector_checklist` 以清單列出上游向量的名稱、來源欄位、Profile 及是否建立向量索引。 |
| `parameters_schema.properties.*.default` | 提供預設值。Embedding、Elasticsearch、Local Search 的 MongoDB 和 Rerank 服務來源預設 `DEV test use`。 |

Dense Embedding 使用一份 `mappings[]` 清單，每筆有 `source_field` 和 `vector_name`。清單至少一筆，預設 `text → text`。讀取舊版 Config 時，原本頂層的映射會轉成清單第一筆。啟用文字組合時，先依 `composition_template` 產生 `composition_field`。模板引用 `{{structdata.欄位}}`，來源須為現有且必填的字串，輸出欄位名稱須唯一。每筆映射都可選該衍生欄位，所有映射共用 Embedding Profile。

`profile` 識別向量空間及模型／版本、維度、文件與查詢的編碼設定。Query Encoder 須與文件向量相容。同時選用多個向量欄位時，每路檢索依其索引綁定的 Profile 進行。

Indexing 的 `vector_fields` 接受要建立索引的具名向量清單。既有的單欄 `vector_name` 仍可讀取，同一有效設定只採其中一種表示。W1 Prototype 的發布模擬使用單欄格式。Embedding 產生多個向量後，Builder 可選擇要讓 Retrieval 搜尋的欄位。

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

System Config 保存 User 的區段選擇、參數引用及實際輸出欄位宣告。模板帶入這些設定的可編輯副本。User 或 AI 助手修改後重新推導與驗證。Remote I/O、參數與錯誤語意見 [Engine](03_engine_and_components.md#remote-api)，環境連線及認證見 [Runtime](06_runtime_api_and_deployment.md#remote-service-deployment)。
