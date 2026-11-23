# W1 Builder 開發契約索引

以下契約可供 Builder 實作表單、API Client 與 Mock。HTTP 物件及狀態代碼見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json)，欄位與列舉的主責入口見 [schemas/](../schemas/README.md)。

[W1 開發基準與待決邊界](08_plan_and_decisions.md#w1-contract-readiness)

| 契約 | 規格與範例 |
|---|---|
| System Config／Component Descriptor | [System Config 規格](05_system_config.md) · [Config Schema](../schemas/system_config.draft.schema.json) · [ES Config 發布請求範例](../examples/system_config/README.md#runtime-http-examples) · [Descriptor 欄位說明](04_component_descriptor.md#descriptor-fields) · [Descriptor Schema](../schemas/component_descriptor.draft.schema.json) · [各模組 Descriptor JSON](../examples/system_config/builder_form.descriptors.json) · [Component 清冊與 Remote 入口](04_component_descriptor.md#prototype-component-inventory) · [表單 Renderer](07_builder_ui.md#descriptor-form-rendering) |
| System 生命週期 API | [初始化、重新載入、更新、狀態與卸載](06_runtime_api_and_deployment.md#system-lifecycle-api) · [選擇 Ingestion／Inference](06_runtime_api_and_deployment.md#runtime-pipeline-deployment) · [DEV 索引遺失與人工恢復](06_runtime_api_and_deployment.md#system-index-lifecycle) · [逐流程卸載](06_runtime_api_and_deployment.md#runtime-system-detach) · [Builder 主動管理 DEV Runtime](06_runtime_api_and_deployment.md#builder-managed-dev-runtimes) · [Builder 部署紀錄草案](drafts/builder_system_deployment_mongodb.md) · [設定來源與保存位置](06_runtime_api_and_deployment.md#runtime-config-sources) |
| 資料生命週期 API | [Ingestion、Run、文件狀態、存在、清單與 Retire](06_runtime_api_and_deployment.md#data-lifecycle-api) · [Pod 內文件占用](06_runtime_api_and_deployment.md#pod-local-ingestion-control) · [工作紀錄保留與清理](06_runtime_api_and_deployment.md#ingestion-status-retention) · [按 Run 批量取消文件](06_runtime_api_and_deployment.md#ingestion-cancel-api) |
| Catalog／Config Validation API | [Catalog](06_runtime_api_and_deployment.md#w1-catalog) · [Catalog 回應範例](../examples/system_config/runtime_catalog.response.json) · [Config Validation](06_runtime_api_and_deployment.md#config-validation-api) |
| Descriptor 推導驗收 | [Builder 與 Engine 的共用規格](04_component_descriptor.md#descriptor-derivation-conformance) · [共用測資](../examples/system_config/descriptor_derivation.fixture.json) |
| Inference API | [查詢 Request／Response](06_runtime_api_and_deployment.md#inference-api) |

[其他設定 → Secret 的 UI 實作](07_builder_ui.md#system-settings-rendering) · [System Secret 設定與匯出範例](../examples/system_config/README.md#system-secret-examples) · [共用 HTTP 與認證](06_runtime_api_and_deployment.md#runtime-http-common) · [錯誤格式與狀態碼](06_runtime_api_and_deployment.md#runtime-http-errors) · [整套 HTTP Mock JSON](../examples/system_config/runtime_http.examples.json)
