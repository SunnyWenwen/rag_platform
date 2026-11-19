# System Config、Component Descriptor 與 Runtime API 範例

這裡提供 Builder 開發用的 JSON 與離線驗證。契約定義見 [System Config](../../docs/05_system_config.md)、[Component Descriptor 欄位說明](../../docs/04_component_descriptor.md#descriptor-fields)和 [Runtime API](../../docs/06_runtime_api_and_deployment.md)。

## 可驗證的 Local Search 設定

- [System Config Schema 草案](../../schemas/system_config.draft.schema.json)驗證發布快照 `{system_id, config_revision, config}`。`config` 包含 `contract_version` 與固定 Module 骨架的 `pipelines`。
- [內建版本](local_memory.builtin.json)及 [Remote Parsing 版本](local_memory.remote_parsing.json)使用同一個 System。第二版只把 Parsing 換成 Remote，兩版推導出相同的候選欄位、向量與索引能力。兩份範例均讓 Chunking 產生 `text`、保留選填的 `price` 和 `tags`，並在 Indexing 啟用 `text.searchable` 與 `price.filterable`。固定 Filter 是 `price gte 300`，可和 [Request 的動態 any 群組](../user_remote_api/inference.request.json) 合併。兩份範例都以 `vector_fields: ["text"]` 選擇一條向量路徑，由索引綁定取得查詢 Profile，路徑上限由 `per_route_k` 設定。

節點以 `component_id` 選執行方式，以 `component_version` 固定版本。內建節點用對應 Descriptor 驗證 `parameters`。使用 `component_id: remote_api` 的節點放在替換區段的第一個 Module，以 `through` 指定最後一個 Module，已涵蓋的後續節點從有效設定省略。Remote Parsing 宣告輸出 `structdata`，Request 依上游 Import 設定推導。Remote 服務以 `service_ref` 引用，Endpoint 由環境綁定解析。Bearer 認證使用節點的 `auth.bearer_token` 和 System Secret。

離線驗證同時檢查 JSON 形狀及跨節點規則。這兩份 Config 使用現行契約版本 `0.2-draft`，涵蓋 Local Search、固定測試 Profile 與內建 Inference。

[IndexBinding JSON](index_binding.example.json) 對應上述兩份 Config 的實際全文、過濾與向量計畫。欄位語意見 [IndexBinding 規格](../../docs/02_data_contracts.md#indexbinding)。

<a id="system-secret-examples"></a>
## System Secret 的 DEV／部署對照

- [DEV 完整 Config](local_memory.remote_parsing.json) 用示意測試值供應 `PARSER_API_TOKEN`、`CHUNK_MAX_TOKENS` 和 `language`。Remote Parser 用 `{{PARSER_API_TOKEN}}` 取得認證值，內建 Chunking 用 `{{CHUNK_MAX_TOKENS}}` 並解析為整數。Remote 的 `{{language}}` 優先使用 [Ingestion Request](../user_remote_api/ingestion.request.json) 傳入的 `zh-TW`，省略時使用 System 值 `en-US`。
- [部署匯出 Config](local_memory.remote_parsing.export.json) 保留相同 Key 與 Module 表達式，`config.secret` 的值以 `null` 表示由環境供應。
- [Deployment 的 env 片段](deployment.secret-env.example.yaml) 映射同名環境變數。憑證使用已建立的 Kubernetes Secret，切分上限和語言使用 ConfigMap。對應規格見 [System Config](../../docs/05_system_config.md#system-secret)及 [Runtime 啟動](../../docs/06_runtime_api_and_deployment.md#system-secret-deployment)。

## Elasticsearch 索引指紋

[索引指紋 v1 範例](index_fingerprint.v1.example.json)示範有效索引設定投影及 ES `mappings._meta` 的 Runtime 欄位。含假設已解析的 Tokenizer 及模型版本。HTTP 範例驗證器會核對兩份 Schema 形狀與範例的 SHA-256。見[索引指紋 v1 規格](../../docs/06_runtime_api_and_deployment.md#index-fingerprint-v1-proposal)。

## Component Descriptor 驗證

- [Meta-schema 草案](../../schemas/component_descriptor.draft.schema.json)驗證 Descriptor 的外層及目前測試的宣告語法。
- [Recursive Descriptor](recursive.descriptor.json)示範切分欄位、由上游 Schema 推導的選項、欄位複製及 overlap 約束。
- [Rewrite Descriptor](rewrite.descriptor.json)用同一個 Component 驗證單筆及多筆改寫、共用 LLM 引用與原始問題選項。
- Python 驗證涵蓋代表性內建鏈、欄位移除後的覆寫失效、IndexBinding、固定與動態 Filter 型別、日期時間、外部候選及 Remote 區段。其他內建方法驗共用外層。IndexBinding 驗證使用符合現行 Schema 的 fixture，檢查全文／向量能力。
- Remote API fixture 涵蓋批次請求、向量輸出與外部檢索候選。實際 Parser、Tokenizer、模型、索引、權限、服務可用性與跨環境部署仍需整合驗收。

從 repo 根目錄執行，Python 需要 jsonschema 4.x。

```sh
python3 examples/system_config/validate_descriptor_draft.py
python3 examples/system_config/validate_runtime_http_examples.py
python3 examples/user_remote_api/validate.py
```

完整 System Config 序列化依 Q-002 定稿。[歷史草案](../../docs/history/superseded/system_config_d66/README.md)保留 D-66 的原始測資。

## Builder 表單 Descriptor

[builder_form.descriptors.json](builder_form.descriptors.json) 涵蓋 Prototype 的 20 個內建 Component。單檔 Prototype 的 `builder-form-descriptors` JSON 區塊內嵌相同描述。更新表單 Descriptor 或內嵌的共用資料 Schema 時同步更新 HTML。離線驗證檢查清冊、控制項型別、可見性及內嵌內容。完整清冊見 [Component Descriptor 手冊](../../docs/04_component_descriptor.md#prototype-component-inventory)。

## Runtime Catalog

[Catalog 回應 JSON](runtime_catalog.response.json)包含 Elasticsearch 範例流程所用的 9 個 Component 和四類環境資源。Builder 依草稿推導欄位候選，並從 Catalog 取得 Profile、Tokenizer、模型及 Elasticsearch 服務選項。見 [Catalog API](../../docs/06_runtime_api_and_deployment.md#w1-catalog)、[Catalog Schema](../../schemas/runtime_catalog.draft.schema.json)和[表單 Renderer](../../docs/07_builder_ui.md#descriptor-form-rendering)。

<a id="runtime-http-examples"></a>
## Builder ↔ Runtime HTTP 範例

[HTTP Request／Response JSON](runtime_http.examples.json)可直接用於 Builder Mock。每步提供 Method、Path、Status，以及該情境的 Body 和 Headers。`body_file` 從同目錄載入完整 JSON，例如 Catalog 回應。實際呼叫所需的認證與 Content-Type 見 [HTTP 共通規格](../../docs/06_runtime_api_and_deployment.md#runtime-http-common)。

| JSON 情境 | 對應規格 |
|---|---|
| `happy_path`，從取得 Catalog、驗證及發布設定，到省略來源版本的匯入、查詢、文件管理及卸載 | [Catalog API](../../docs/06_runtime_api_and_deployment.md#w1-catalog) · [Config Validation API](../../docs/06_runtime_api_and_deployment.md#config-validation-api) · [System 生命週期](../../docs/06_runtime_api_and_deployment.md#system-lifecycle-api) · [資料生命週期](../../docs/06_runtime_api_and_deployment.md#data-lifecycle-api) |
| `reuse_and_rebuild`、`blocked_or_stale_publish`，涵蓋索引沿用／重建、欄位錯誤及版本衝突 | [System 生命週期](../../docs/06_runtime_api_and_deployment.md#system-lifecycle-api) · [索引重建](../../docs/06_runtime_api_and_deployment.md#system-index-lifecycle) · [錯誤格式](../../docs/06_runtime_api_and_deployment.md#runtime-http-errors) |
| `ingestion_status_and_errors`，涵蓋無效請求、文件忙碌、Run 部分失敗及紀錄過期 | [資料生命週期](../../docs/06_runtime_api_and_deployment.md#data-lifecycle-api) |
| `query_empty_and_errors`，涵蓋無命中、無效 Filter、索引未就緒及上游失敗 | [Inference API](../../docs/06_runtime_api_and_deployment.md#inference-api) |
| `document_pagination`，涵蓋沿用 `next_cursor`、最後一頁及無效 Cursor | [文件摘要清單](../../docs/06_runtime_api_and_deployment.md#src-21-93-文件摘要清單d-65-已確認核心) |

以 `validate_runtime_http_examples.py` 檢查測資 Schema 與跨步驟關聯。實際 HTTP、Elasticsearch 與模型由 DEV 環境串接驗收。
