# 現行共用 Schema

此目錄定義機器可讀契約的欄位、固定選項及狀態代碼。文件說明執行語意，範例和驗證工具引用對應 Schema。[Builder → DEV Runtime OpenAPI](../openapi/runtime.dev.v1.json) 定義 HTTP 操作並引用本目錄的物件 Schema。

| Schema | 用途與欄位說明 |
|---|---|
| [data_meta](data_meta.schema.json) | [structdata 欄位型別、必填性、搜尋旗標與 Indexing 覆寫](../docs/02_data_contracts.md#data-meta-schema) |
| [document](document.schema.json) | [Document 外層、content、DenseVector 與檢索候選](../docs/02_data_contracts.md#document) |
| [ingestion_request](ingestion_request.schema.json) | [非空 documents 和共用 parameters](../docs/06_runtime_api_and_deployment.md#src-21-3-ingestion-的提交與接收) |
| [ingestion_cancel_request](ingestion_cancel_request.schema.json) | [指定 Run 中要取消的 document_ids](../docs/06_runtime_api_and_deployment.md#ingestion-cancel-api) |
| [inference_request](inference_request.schema.json) | [query、filters、metadata、parameters](../docs/06_runtime_api_and_deployment.md#inference-api) |
| [remote_api](remote_api.schema.json) | [Remote API 共用 v1 封裝、追蹤 Header、成功與錯誤](../docs/03_engine_and_components.md#remote-api) |
| [query_context](query_context.schema.json) | [QueryContext[] 與 ResultItem.data 候選 Document](../docs/02_data_contracts.md#inference-contract) |
| [elasticsearch_connection](elasticsearch_connection.schema.json) | [Elasticsearch 服務來源、PLED 連線欄位和密碼引用](../docs/05_system_config.md#elasticsearch-service-source) |
| [index_binding](index_binding.schema.json) | [平台管理索引的格式、位置及能力](../docs/02_data_contracts.md#indexbinding) |
| [index_fingerprint.v1](index_fingerprint.v1.schema.json) | [ES 索引相容性指紋投影與 mapping metadata](../docs/06_runtime_api_and_deployment.md#index-fingerprint-v1-proposal) |
| [runtime_identity](runtime_identity.schema.json) | [System ID、索引世代及部署環境識別](../docs/06_runtime_api_and_deployment.md#runtime-index-ownership) |
| [runtime_http](runtime_http.schema.json) | [管理與業務 API 的 HTTP 物件、分頁參數及狀態代碼](../docs/06_runtime_api_and_deployment.md#runtime-http-common)，含 [Inference 成功物件](runtime_http.schema.json#/$defs/inference_response) |
| [runtime_catalog](runtime_catalog.draft.schema.json) | [W1 Runtime 的 Descriptor 與環境資源清單](../docs/06_runtime_api_and_deployment.md#w1-catalog) |
| [component_descriptor](component_descriptor.draft.schema.json) | [內建 Component 的識別、參數、推導與 UI 規則](../docs/04_component_descriptor.md#descriptor-fields) |
| [config_enums](config_enums.schema.json) | [內建 Component 固定選項的儲存代碼](../docs/05_system_config.md#config-enums) |
| [system_config](system_config.draft.schema.json) | [有效 Config 快照、Variable／Secret 與 Pipeline 節點](../docs/05_system_config.md#config-fields) |
| [MongoDB Builder System 生命週期](mongodb/builder_system_lifecycle.validator.json) | [權威索引綁定及 System 層級操作計畫](../docs/drafts/builder_system_deployment_mongodb.md#system-層級權威紀錄) |
| [MongoDB Builder 部署紀錄 validator](mongodb/builder_system_deployment.validator.json) | [部署意圖與逐流程狀態、待確認操作和觀測紀錄](../docs/drafts/builder_system_deployment_mongodb.md#collection-欄位) |

System 的有效欄位與執行參數由設定細化。共用 Schema 驗證資料形狀，編譯器再檢查 System 的型別、必填性、引用、相依及索引能力。Schema URI 由本地 Registry 解析。見 [System Config／Descriptor 驗證](../examples/system_config/README.md)和 [Remote API 驗證](../examples/user_remote_api/README.md)。舊資料契約收錄於[歷史契約快照](../docs/history/superseded/legacy_contracts/README.md)。
