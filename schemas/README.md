# 現行共用 Schema

| Schema | 用途與欄位說明 |
|---|---|
| [data_meta](data_meta.schema.json) | [structdata 欄位型別、必填性、搜尋旗標與 Indexing 覆寫](../docs/02_data_contracts.md#data-meta-schema) |
| [document](document.schema.json) | [Document 外層、content、DenseVector 與檢索候選](../docs/02_data_contracts.md#document) |
| [ingestion_request](ingestion_request.schema.json) | [非空 documents 和共用 parameters](../docs/06_runtime_api_and_deployment.md#src-21-3-ingestion-的提交與接收) |
| [inference_request](inference_request.schema.json) | [query、filters、metadata、parameters](../docs/06_runtime_api_and_deployment.md#inference-api) |
| [query_context](query_context.schema.json) | [QueryContext[] 與 ResultItem.data 候選 Document](../docs/02_data_contracts.md#inference-contract) |
| [index_binding](index_binding.schema.json) | [平台管理索引的格式、位置及能力](../docs/02_data_contracts.md#indexbinding) |
| [index_fingerprint.v1](index_fingerprint.v1.schema.json) | [ES 索引相容性指紋投影與 mapping metadata](../docs/06_runtime_api_and_deployment.md#index-fingerprint-v1-proposal) |
| [runtime_catalog](runtime_catalog.draft.schema.json) | [W1 Runtime 的 Descriptor 與環境資源清單](../docs/06_runtime_api_and_deployment.md#w1-catalog) |
| [component_descriptor](component_descriptor.draft.schema.json) | [內建 Component 的識別、參數、推導與 UI 規則](../docs/04_component_descriptor.md#descriptor-fields) |
| [system_config](system_config.draft.schema.json) | [有效 Config 快照、System Secret 與 Pipeline 節點](../docs/05_system_config.md#config-fields) |

System 的有效欄位與執行參數由設定細化。共用 Schema 驗證資料形狀，編譯器再檢查 System 的型別、必填性、引用、相依及索引能力。Schema URI 由本地 Registry 解析。見 [System Config／Descriptor 驗證](../examples/system_config/README.md)和 [Remote API 驗證](../examples/user_remote_api/README.md)。舊資料契約收錄於[歷史契約快照](../docs/history/superseded/legacy_contracts/README.md)。
