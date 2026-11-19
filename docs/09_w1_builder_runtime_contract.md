# W1 Builder 開發契約索引

以下契約可供 Builder 實作表單、API Client 與 Mock。

[W1 開發基準與待決邊界](08_plan_and_decisions.md#w1-contract-readiness)

| 契約 | 規格與範例 |
|---|---|
| System Config／Component Descriptor | [System Config 規格](05_system_config.md) · [Config Schema](../schemas/system_config.draft.schema.json) · [Config 範例](../examples/system_config/README.md#可驗證的-local-search-設定) · [Descriptor 欄位說明](04_component_descriptor.md#descriptor-fields) · [Descriptor Schema](../schemas/component_descriptor.draft.schema.json) · [各模組 Descriptor JSON](../examples/system_config/builder_form.descriptors.json) · [Component 清冊與 Remote 入口](04_component_descriptor.md#prototype-component-inventory) · [表單 Renderer](07_builder_ui.md#descriptor-form-rendering) |
| System 生命週期 API | [初始化、更新、列出、狀態與卸載](06_runtime_api_and_deployment.md#system-lifecycle-api) |
| 資料生命週期 API | [Ingestion、Run、文件狀態、存在、清單與 Retire](06_runtime_api_and_deployment.md#data-lifecycle-api) |
| Catalog／Config Validation API | [Catalog](06_runtime_api_and_deployment.md#w1-catalog) · [Catalog 回應範例](../examples/system_config/runtime_catalog.response.json) · [Config Validation](06_runtime_api_and_deployment.md#config-validation-api) |
| Inference API | [查詢 Request／Response](06_runtime_api_and_deployment.md#inference-api) |

[其他設定 → Secret 的 UI 實作](07_builder_ui.md#system-settings-rendering) · [System Secret 設定與匯出範例](../examples/system_config/README.md#system-secret-examples) · [共用 HTTP 與認證](06_runtime_api_and_deployment.md#runtime-http-common) · [錯誤格式與狀態碼](06_runtime_api_and_deployment.md#runtime-http-errors) · [整套 HTTP Mock JSON](../examples/system_config/runtime_http.examples.json)
