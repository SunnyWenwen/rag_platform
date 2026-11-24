# 規格條文對照表（rag_platform 06）

把 06 中規定「回什麼代碼、狀態必須怎樣」的條文逐條對到測試。改到相關程式或規格時，先找到對應的列；新增條文時加一列。沒有測試的條文寫明原因，不留空白。

範圍：System 生命週期、索引生命週期、Pod 內匯入控制、取消、Retire、查詢限制、錯誤表。測試檔都在 `tests/`。

## System 生命週期（06#system-lifecycle-api）

| 條文 | 測試 |
|---|---|
| PUT 完成套用回 `200`＋`SystemStatus`；同一 `Idempotency-Key` 同內容重送回原結果，不同內容回 `409 IDEMPOTENCY_CONFLICT` | `test_runtime_flow.py::test_apply_is_idempotent_and_rejects_stale_context` |
| 同程序仍在處理同一操作時，重送先等結果；其他操作回 `409 SYSTEM_BUSY` | `test_lifecycle_rules.py::test_resend_during_the_operation_waits_for_its_result` |
| `context_revision` 綁定目標、Catalog、Config、草稿、流程、操作、預期綁定、預檢結果；不符回 `409 STALE_CONTEXT`；Catalog 不符回 `409 STALE_CATALOG` | `test_lifecycle_safety.py::test_context_revision_binds_operation_and_draft`、`test_runtime_flow.py::test_apply_is_idempotent_and_rejects_stale_context` |
| GET 無綁定 Header：觀察本機；重啟後未載入回 `404 SYSTEM_NOT_FOUND` | `test_lifecycle_rules.py::test_reload_after_restart_reconnects_the_existing_index` |
| GET 帶綁定：查核成功回 `200`＋`loaded: false`；指定世代不存在且未載入回 `404` | 同上；`test_lifecycle_safety.py::test_unloaded_system_on_another_cluster_is_not_reported_missing` |
| GET 帶綁定：本機仍載入而索引已遺失，回 `index_ready: false`、`index_generation: null` | `test_lifecycle_rules.py::test_recover_index_after_the_index_is_lost` |
| GET 帶綁定：`created_by_operation_id` 取自指定索引，載入與就緒取本機 | `test_lifecycle_safety.py::test_get_reports_the_creator_of_the_specified_index` |
| 查核結果不明（未載入且索引可能在 PLED 叢集）回 `503 SYSTEM_STATE_UNKNOWN` | `test_lifecycle_safety.py::test_unloaded_system_on_another_cluster_is_not_reported_missing` |
| GET 清單列出本機已載入的 System | `test_lifecycle_rules.py::test_list_systems` |
| `busy` 在有操作進行、匯入工作或重建待續時為 `true` | `test_lifecycle_rules.py::test_work_in_progress_blocks_detach_delete_and_retire`、`test_lifecycle_safety.py::test_failed_rebuild_reports_not_ready_and_resumes_with_the_same_operation` |
| Inference 指定 `initialize`／`update`／`recover_index`：預檢 `blocked`＋`PIPELINE_OPERATION_UNSUPPORTED`，PUT 回 `409` | `test_lifecycle_rules.py::test_inference_only_reloads`（以 `initialize` 驗證；三者共用同一判斷） |
| 先 `initialize`＋`ingestion`，再 `reload`＋`inference` | 同上 |
| A `initialize`：已有生效版本或已載入時，預檢與 PUT 都回 `SYSTEM_STATE_CONFLICT` | `test_lifecycle_rules.py::test_initialize_twice_is_a_state_conflict` |
| 成功的建立在重啟後以同一操作重送，靠 `created_by_operation_id` 認回自己的索引；其他操作不得認領 | `test_lifecycle_rules.py::test_initialize_resent_after_a_restart_reuses_its_own_index` |
| B `reload`：接回既有索引；Config 不相容時 `blocked`（`INDEX_RECONNECT_INCOMPATIBLE`） | `test_lifecycle_rules.py::test_reload_after_restart_reconnects_the_existing_index`、`test_reload_with_an_incompatible_config_is_blocked` |
| C `update`：相容沿用；需重建回 `rebuild_required`，未確認回 `409 REBUILD_CONFIRMATION_REQUIRED` | `test_runtime_flow.py::test_update_reuses_or_requires_rebuild_confirmation` |
| C `update`：預期生效版本不符回 `409 REVISION_CONFLICT` | `test_lifecycle_rules.py::test_expected_binding_mismatches` |
| 預期索引綁定須是本機已載入的綁定；指向同 System 的另一個世代時，刪除或切換前回 `409 INDEX_CONFLICT` | `test_review_round3.py::test_update_against_another_generation_is_refused_before_any_delete` |
| `reload` 相同版本與世代但值不同（例如換密碼）時使用新值 | `test_review_round3.py::test_reload_after_detach_uses_rotated_credentials` |
| C `update`：合法 mapping 變更是 `rebuild_required`；舊索引與生效版本不符時仍 `INDEX_OWNERSHIP_UNVERIFIED` | `test_lifecycle_safety.py::test_mapping_change_previews_as_rebuild_and_tampering_still_blocks` |
| C `update`：已開始的查詢固定舊版到結束 | `test_lifecycle_rules.py::test_running_query_keeps_the_old_version` |
| 重建：刪除任何索引前確認目標世代是新的且未被其他操作建立，否則 `409 INDEX_CONFLICT` 且服務不變 | `test_lifecycle_safety.py::test_rebuild_checks_the_target_before_deleting_anything` |
| 重建中斷：未就緒、`busy`；同一操作重送續建；重啟後依原計畫重做預檢與 PUT 也能續建；其間其他 PUT、DELETE、detach 回 `409 SYSTEM_BUSY` | `test_lifecycle_safety.py::test_failed_rebuild_reports_not_ready_and_resumes_with_the_same_operation`、`test_half_done_rebuild_blocks_delete_and_resumes_after_a_restart` |
| D DELETE：關入口、排空、刪索引、`204`；之後 GET `404` | `test_runtime_flow.py::test_publish_ingest_query_and_manage_documents` |
| D DELETE：本機有未結算作業回 `409 SYSTEM_BUSY` | `test_lifecycle_rules.py::test_work_in_progress_blocks_detach_delete_and_retire` |
| D DELETE：受管索引必須帶預期世代與指紋，缺任一項在關入口或刪除前回 `422` | `test_review_round3.py::test_delete_without_generation_or_fingerprint_is_refused` |
| detach：先關入口；Ingestion 有工作回 `409 SYSTEM_BUSY`；同一操作重送回 `204` | 同上；`test_lifecycle_safety.py::test_upload_read_during_detach_is_refused` |
| detach：版本不符 `409 REVISION_CONFLICT`，世代不符 `409 INDEX_CONFLICT` | `test_lifecycle_rules.py::test_expected_binding_mismatches` |
| detach Inference：等查詢結束；逾時回 `504 DEADLINE_EXCEEDED` 並恢復入口 | `test_lifecycle_rules.py::test_detach_inference_times_out_and_reopens`、`test_lifecycle_safety.py::test_detaching_both_pipelines_closes_ingestion_while_queries_drain` |
| `recover_index`：原索引仍在時 `blocked`；確認遺失後以新世代建立；`config_revision` 須等於 `recovery_from.config_revision`（否則 `422`） | `test_lifecycle_rules.py::test_recover_index_after_the_index_is_lost` |
| `recover_index`：`recovery_from` 必須指向預期的已發布綁定（世代與版本），否則 `422` | `test_review_round3.py::test_recover_index_cannot_point_away_from_the_published_binding` |
| 獨立部署分 Pod：只需注入自己流程的 System API 帳密（05） | `test_review_round3.py::test_inference_only_pod_needs_only_inference_credentials` |
| 獨立部署：索引歸屬正確但實際 mapping 不符時不開放（not ready） | `test_review_round3.py::test_standalone_index_with_a_wrong_mapping_is_not_ready` |
| ES 換密碼使用新連線 | `test_lifecycle_safety.py::test_es_clients_follow_password_rotation` |

## Pod 內匯入控制、取消與 Retire

| 條文 | 測試 |
|---|---|
| 整批預檢通過才 `202`＋`Location`；欄位錯誤定位、重複 `document_id`、非法 JSON | `test_runtime_flow.py::test_publish_ingest_query_and_manage_documents`、`test_ingestion_rejects_invalid_documents` |
| 管理操作關閉入口後，讀完 body 的請求不得入列 | `test_lifecycle_safety.py::test_upload_read_during_detach_is_refused` |
| 整批占用衝突回 `409 DOCUMENT_BUSY`＋全部衝突清單 | `test_ingestion_control.py::test_cancel_reports_cancelled_and_cancelling` |
| Queue 容量不足回 `503 RUNTIME_CAPACITY_EXHAUSTED` | `test_ingestion_control.py::test_full_queue_answers_runtime_capacity_exhausted` |
| 執行中的 Retire 計入本機總量 | `test_ingestion_control.py::test_retire_takes_a_slot_of_the_pod_total` |
| 取消表：`cancelled`、`cancelling`、`already_finished`、`not_found`；Run 不存在回 `404 INGESTION_RUN_NOT_FOUND` | `test_ingestion_control.py::test_cancel_reports_cancelled_and_cancelling`、`test_unknown_run_and_retention` |
| 取消表：結果待查的 `unknown` 回 `not_cancellable` | `test_ingestion_control.py::test_cancel_of_an_unknown_document_is_not_cancellable` |
| Bulk 逾時：文件 `failed`（`ES_BULK_TIMEOUT`），可重送 | `test_ingestion_control.py::test_bulk_timeout_fails_document_and_allows_retry` |
| 同文件重送以新 `write_id` 取代舊批次 | `test_ingestion_control.py::test_resubmission_replaces_previous_chunks` |
| 新舊批次同時可見時（D-60 允許），同一份結果清單不重複 `data_id` | `test_review_round3.py::test_no_duplicate_data_id_while_old_and_new_batches_are_visible` |
| 已結束的 Run 不保留舊版 Config（Snapshot 與兩張 LangGraph），切版後可回收 | `test_review_round3.py::test_finished_runs_release_the_old_snapshot` |
| 清舊或 Retire 的刪除未完整確認（逾時、failures、version_conflicts）視為不明 | `test_es_store.py::test_partial_deletes_are_not_reported_as_done`、`test_lifecycle_safety.py::test_retire_reports_an_unconfirmed_delete` |
| 紀錄保留期與數量上限、重啟後 `unknown` | `test_ingestion_control.py::test_unknown_run_and_retention` |
| Retire 回 `deleted`／`not_found`；文件仍在處理時 `409 DOCUMENT_BUSY` | `test_runtime_flow.py::test_publish_ingest_query_and_manage_documents`、`test_lifecycle_rules.py::test_work_in_progress_blocks_detach_delete_and_retire` |

## 查詢限制、Health、認證與錯誤表

| 條文 | 測試 |
|---|---|
| 每 System 速率與併發額滿回 `429 RATE_LIMITED`＋`Retry-After`，不排隊 | `test_request_limits.py::test_per_system_rate_limit`、`test_per_system_concurrency_rejects_at_once` |
| 整個 Runtime 併發額滿回 `503 RUNTIME_CAPACITY_EXHAUSTED` | `test_request_limits.py::test_runtime_wide_concurrency_is_503` |
| 查詢期限逾時回 `504 DEADLINE_EXCEEDED` 並歸還名額 | `test_request_limits.py::test_query_deadline` |
| 查詢回應帶 `X-Config-Revision`、`X-Index-Generation` | `test_runtime_flow.py::test_publish_ingest_query_and_manage_documents` |
| Health 免認證；未就緒回 `503 RUNTIME_NOT_READY` | `test_runtime_flow.py::test_health_needs_no_credentials`、`test_standalone.py::test_standalone_is_not_ready_without_its_index` |
| 管理、Ingestion、Inference 帳密不可交叉使用（`401`） | `test_runtime_flow.py::test_management_routes_need_management_credentials`、`test_business_routes_check_pipeline_credentials` |
| `X-Request-Id` 沿用或產生 | `test_runtime_flow.py::test_request_id_is_echoed_or_generated` |
| `413 BODY_TOO_LARGE`、`415 UNSUPPORTED_MEDIA_TYPE`、`400 INVALID_JSON`、`422` 定位 | `test_lifecycle_rules.py::test_body_size_and_media_type`、`test_runtime_flow.py::test_ingestion_rejects_invalid_documents`、`test_config_errors_are_located` |
| MCP 使用同一入口與 Inference 帳密 | `test_mcp.py::test_mcp_search_tool` |

## 沒有測試的條文

| 條文 | 原因 |
|---|---|
| 多個 Runtime 之間的排空、切版與共用索引 | 隨多 Runtime 後續啟用（rag_platform `todo_enhance.md#dev-multi-runtime`），v1 只有一個 DEV Runtime |
| ES 操作超過期限「可」回 `504` | 規格為可選；目前 ES 錯誤回 `503 SYSTEM_STATE_UNKNOWN` |
| 已卸載且可確認原綁定時 detach「也可」回 `204` | 規格為可選；未載入時回 `404 SYSTEM_NOT_FOUND` |
| SIGTERM 優雅關閉、FTEST／ENT 首次建立索引 | 規格列為後續（`todo_enhance.md`） |
| Builder 端的重試、待確認紀錄與補載 | Builder 的責任，不在 Runtime |
| 真實 ES／bge-m3／LLM 的行為 | 需要公司環境，見 [testing.md](testing.md) 第 3、4 層 |
