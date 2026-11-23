# W1 Builder 開發契約索引

以下契約可供 Builder 實作表單、API Client 與 Mock。HTTP 物件及狀態代碼見 [Runtime HTTP Schema](../schemas/runtime_http.schema.json)，欄位與列舉的主責入口見 [schemas/](../schemas/README.md)。

[W1 開發基準與待決邊界](08_plan_and_decisions.md#w1-contract-readiness)

<a id="builder-runtime-quickstart"></a>
## 本機串接

1. Builder Backend 實作用於 DEV 的 API Client，操作與認證以 [Builder → DEV Runtime OpenAPI](../openapi/runtime.dev.v1.json) 為準。若工具需要單檔，先在 repo 根目錄產生可離線匯入的 OpenAPI。
   ```sh
   python3 examples/system_config/build_runtime_openapi.py runtime.dev.v1.openapi.json
   ```
2. 在另一個終端啟動 [Mock Runtime](../examples/system_config/README.md#mock-runtime)。Builder Backend 的 Base URL 設為 `http://127.0.0.1:8000`，本機 Basic 帳密為 `mock:mock`。
   ```sh
   python3 examples/system_config/mock_runtime.py --scenario happy_path
   ```
   以 [`happy_path`](../examples/system_config/runtime_http.examples.json) 的 System Config 及資料串通 Catalog → 預檢與發布 → 匯入及 Run 輪詢 → 查詢。取得 `202` 後沿用同一目標的 `Location`。要試切版、匯入失敗或查詢錯誤時，切換到對應情境。
3. 執行 [HTTP 情境契約測試](../tests/README.md#dev-runtime-http-contract-test)。測試會自行啟動 Mock，依序重播每組情境，檢查 HTTP 回應、OpenAPI Schema 和各步驟的狀態關聯。DEV 接線使用 `http://dev-runtime` 這類 Service URL、部署提供的 Basic 帳密與 Builder ServiceAccount，依 [Istio 傳輸規格](06_runtime_api_and_deployment.md#istio-http-transport)驗收。

| 契約 | 規格與範例 |
|---|---|
| System Config／Component Descriptor | [System Config 規格](05_system_config.md) · [Config Schema](../schemas/system_config.draft.schema.json) · [ES Config 發布請求範例](../examples/system_config/README.md#runtime-http-examples) · [Descriptor 欄位說明](04_component_descriptor.md#descriptor-fields) · [Descriptor Schema](../schemas/component_descriptor.draft.schema.json) · [各模組 Descriptor JSON](../examples/system_config/builder_form.descriptors.json) · [Component 清冊與 Remote 入口](04_component_descriptor.md#prototype-component-inventory) · [表單 Renderer](07_builder_ui.md#descriptor-form-rendering) |
| System 層級紀錄 | [Builder 權威綁定與待確認操作](drafts/builder_system_deployment_mongodb.md#system-層級權威紀錄) · [刪除前的 Inference 排空](06_runtime_api_and_deployment.md#builder-query-drain) |
| System 生命週期 API | [初始化、重新載入、更新、狀態與卸載](06_runtime_api_and_deployment.md#system-lifecycle-api) · [選擇 Ingestion／Inference](06_runtime_api_and_deployment.md#runtime-pipeline-deployment) · [DEV 索引遺失與人工恢復](06_runtime_api_and_deployment.md#system-index-lifecycle) · [逐流程卸載](06_runtime_api_and_deployment.md#runtime-system-detach) · [Builder 主動管理 DEV Runtime](06_runtime_api_and_deployment.md#builder-managed-dev-runtimes) · [Builder 部署紀錄草案](drafts/builder_system_deployment_mongodb.md) · [設定來源與保存位置](06_runtime_api_and_deployment.md#runtime-config-sources) |
| 資料生命週期 API | [Ingestion、Run、文件狀態、存在、清單與 Retire](06_runtime_api_and_deployment.md#data-lifecycle-api) · [Pod 內文件占用](06_runtime_api_and_deployment.md#pod-local-ingestion-control) · [工作紀錄保留與清理](06_runtime_api_and_deployment.md#ingestion-status-retention) · [按 Run 批量取消文件](06_runtime_api_and_deployment.md#ingestion-cancel-api) |
| Catalog／Config Validation API | [Catalog](06_runtime_api_and_deployment.md#w1-catalog) · [Catalog 回應範例](../examples/system_config/runtime_catalog.response.json) · [Config Validation](06_runtime_api_and_deployment.md#config-validation-api) |
| Descriptor 推導驗收 | [Builder 與 Engine 的共用規格](04_component_descriptor.md#descriptor-derivation-conformance) · [共用測資](../examples/system_config/descriptor_derivation.fixture.json) |
| System 與索引識別 | [UUID、部署環境與 ES 歸屬](06_runtime_api_and_deployment.md#runtime-index-ownership) · [建立與拒絕案例](../examples/system_config/index_fingerprint.v1.example.json) |
| Elasticsearch 來源 | [連線欄位與 Secret 規格](05_system_config.md#elasticsearch-service-source) · [PLED ES 設定與部署範例](../examples/system_config/README.md#pled-elasticsearch-example) |
| Inference API | [查詢 Request／Response](06_runtime_api_and_deployment.md#inference-api) · [成功回應 Schema](../schemas/runtime_http.schema.json#/$defs/inference_response) |
| 文件／切片識別與評估 | [Document ID、Data ID](02_data_contracts.md#document-identities) · [CSV 與檔案主鍵](07_builder_ui.md#builder-source-document-id) · [文件層級排名](03_engine_and_components.md#document-level-evaluation) |
| User Remote API | [v1 契約](03_engine_and_components.md#remote-api) · [OpenAPI](../examples/user_remote_api/openapi.json) · [JSON 範例與驗證](../examples/user_remote_api/README.md) |

[其他設定 → Variable 與 Secret](07_builder_ui.md#system-settings-rendering) · [Variable／Secret 設定與匯出範例](../examples/system_config/README.md#system-secret-examples) · [共用 HTTP 與認證](06_runtime_api_and_deployment.md#runtime-http-common) · [錯誤格式與狀態碼](06_runtime_api_and_deployment.md#runtime-http-errors) · [整套 HTTP Mock JSON](../examples/system_config/runtime_http.examples.json)
