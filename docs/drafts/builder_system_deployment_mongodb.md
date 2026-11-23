# Builder System 部署狀態與 MongoDB Collection 草案

Builder 保存 System、所有 Config Revision 及各目標 Runtime 的部署意圖，並[主動管理 DEV Runtime](../06_runtime_api_and_deployment.md#builder-managed-dev-runtimes)的發布與重啟後補載。DEV 首版每個 Runtime 以一個 Pod 執行，在記憶體中持有已載入的 Config、執行物件與本地 Queue。Builder 保存 System 層級的權威綁定與操作計畫。Runtime 以 ES 資料索引查核實體狀態。Ingestion Run 留在受理 Pod 的記憶體。獨立部署由匯出的 Config 啟動。

## Collection 欄位

Collection 名稱為 `builder_system_deployments`。每個 `(environment, runtime_ref, system_id)` 一筆，唯一鍵由三欄組成。Builder 管理的 Runtime 使用固定環境識別 `builder`，`runtime_ref` 取自部署目標。環境與 System ID 格式見 [Runtime 識別規格](../06_runtime_api_and_deployment.md#runtime-index-ownership)。同一目標的 Runtime 重啟或更換 Pod 時沿用 `runtime_ref`。完整 Config 依 `system_id` 與 `config_revision` 從 Builder 的 Config Revision 紀錄讀取。單純儲存或驗證草稿不建立部署紀錄。

Builder 在同一筆目標紀錄中追蹤兩條流程的部署意圖。分 Pod 時各 Runtime 各有一筆，使用同一份完整 Config 與受管 ES 索引。各目標共用同一筆 Builder System 綁定。逐流程部署見 [Runtime 契約](../06_runtime_api_and_deployment.md#runtime-pipeline-deployment)。

| 欄位 | BSON 型別 | 定義 |
|---|---|---|
| `_id` | ObjectId | MongoDB Document ID。 |
| `environment`、`runtime_ref`、`system_id` | String | 環境、Runtime 部署目標及 Builder 配發的 System 識別。 |
| `schema_version` | Int32 | Document 格式版本，初版為 `1`。 |
| `state_version` | Int64 | Builder 條件更新的版本，初始為 `0`，成功更新時加一。避免較舊的同步結果覆寫新的操作。 |
| `desired_pipelines` | Object | 以 `ingestion`、`inference` 為鍵，各保存最近確認的部署意圖。每項含 `state`、`config_revision`、`confirmed_at`。`online` 保存預期部署的發布版本，`unloaded` 的版本為 `null`。仍未確認意圖的流程為 `null`。 |
| `desired` | Object / Null | 相容舊部署紀錄。讀取時將原整組意圖套到兩條流程，首次條件更新以 `desired_pipelines` 取代。新紀錄使用 `desired_pipelines`。 |
| `pending_operation` | Object / Null | 已發起且尚無確認結果的操作，含 `operation_id`、`kind`、選填 `pipeline`、`target_config_revision`、`expected_active_revision`、`expected_index_generation`、`apply_context`、`allow_rebuild`、`started_at`。`pipeline` 保存原請求目標，省略表示整組操作。`unload` 對應 System DELETE，省略 `pipeline`。`detach` 與 `unload` 的目標版本為 `null`；`recover_index` 以原發布版本與遺失索引世代為前置條件。`allow_rebuild` 只在已確認重建的 `update` 使用 `true`。各目標的觀測與排空進度獨立保存；跨目標的互斥由 System 層級紀錄提供。三個索引欄位 `expected_index_fingerprint`、`target_index_generation`、`target_index_fingerprint` 保存原指紋與預定新綁定。 |
| `pending_operation.apply_context` | Object / Null | 保存 PUT 原預檢的 `draft_revision`、`catalog_revision`、`context_revision`，搭配發布快照重送同一操作。`detach` 與 DELETE 為 `null`，使用待確認紀錄中的預期版本及世代。若原快照或驗證條件無法重現，先查操作結果。 |
| `last_observation` | Object / Null | Builder 最後取得的 Runtime 狀態，含 `state`、`observed_at`、`system_status`。從未查核時為 `null`，連線失敗則記 `unreachable`。`200` 時保存完整的 [SystemStatus](../06_runtime_api_and_deployment.md#system-lifecycle-api)，依其 `loaded` 選擇 `loaded` 或 `not_loaded`。`404` 也記為 `not_loaded`，`system_status` 則為 `null`。Runtime 回報狀態待查時為 `unknown`。 |
| `last_confirmed_index_generation` | String / Null | 最近一次確認就緒的受管索引世代。連線失敗、查無載入或索引待查時保留，供後續比對。單目標 `detach` 後保留，DELETE 確認清除索引後清除。 |
| `created_at`、`updated_at` | Date | 部署紀錄建立、最後更新的 UTC 時間。 |

```javascript
db.builder_system_deployments.createIndex(
  { environment: 1, runtime_ref: 1, system_id: 1 },
  { unique: true, name: "uq_builder_system_deployment" }
)
```

[MongoDB Collection validator](../../schemas/mongodb/builder_system_deployment.validator.json) 定義欄位型別及狀態組合。

## System 層級權威紀錄

Builder 以 `(environment, system_id)` 建立唯一索引，於 `builder_system_lifecycle` 保存已提交的 `active_config_revision`、`index_generation` 和 `index_fingerprint`。操作對象及原請求計畫保存在 `pending_operation`，由 `state_version` 條件更新取得同一 System 的操作權。非受管索引的世代與指紋為 `null`。目標 Runtime 的觀測結果不能直接覆蓋本紀錄。見 [System 紀錄 validator](../../schemas/mongodb/builder_system_lifecycle.validator.json)。

全域操作進行中的 `detach` 屬暫停服務，Builder 在 pending operation 的 drained_targets 保存 runtime_ref、pipeline、查核方法與時間，並保留原部署意圖，以便成功後載回。Builder 重啟先讀全域計畫與目標進度再繼續。對失聯的寫入目標，確認部署層的停止或隔離與未結算操作後才清除或接手，且操作持有期間禁止自動補載。

## 發布與同步

1. Builder 先以 System 層級條件更新保存不可變 Config Revision 與包含目標流程的 `pending_operation`，再以 `operation_id` 作為 `Idempotency-Key` 送出請求。收到明確成功後，以一次條件更新提交該操作的部署意圖並清除待確認紀錄。`detach` 只將指定流程設為 `unloaded`；明確重新部署後，`reload` 成功才將指定流程設回 `online`。逐流程 `update` 和 `recover_index` 保留上線／卸載意圖。DELETE 成功代表 System 索引已刪除，更新所有受影響的部署。
2. Builder Backend 定期以單一 System GET 及已知綁定 Header 逐目標核對 `desired_pipelines` 和 `SystemStatus.pipelines`。預設每 60 秒，可由 Builder 部署設定調整，Builder 啟動及 Runtime 恢復連線後也查核。預期上線但未載入有效快照時，以已發布 Config 預檢並呼叫 `reload`。補載使用 System 的共用生效版本及索引世代；遇到部署紀錄仍指向舊版時，先查核 System 的發布結果。
3. 逾時或中斷時保留 `pending_operation`，查核舊、新世代與建立操作標記，並以同一操作鍵、版本和 `pipeline` 查核。`detach` 待確認期間暫停目標流程補載。DELETE 待確認期間暫停相關 Runtime 的補載及索引恢復。明確失敗後可清除該次待處理操作並保留原部署意圖。
4. 確認索引遺失時，Builder 回報異常並保留部署意圖和最後確認世代。使用者確認後才向 Ingestion Runtime 發起 `recover_index`。成功時以索引世代更新確認結果，對仍預期上線的流程逐一 `reload`，依[初次匯入規則](../07_builder_ui.md#builder-initial-ingestion-readiness)安排重新匯入。
5. Runtime 回報 Builder 無法對應的生效版本時，保留差異供查核。Runtime 無法連線時保留部署意圖及待確認操作。需要重新發起操作時先結算原操作，再重驗 Config 與索引影響。新出現的破壞性影響須另行確認。

`desired_pipelines` 是 Builder 用來重啟後重新載入的目標，`last_observation` 記錄最近一次 Runtime 查詢結果。操作前置條件、恢復流程及重送語意見 [System 生命週期 API](../06_runtime_api_and_deployment.md#system-lifecycle-api)。

## 已發布的紀錄範例

以下使用 MongoDB Extended JSON 表示 BSON 值。

```json
{
  "_id": {"$oid": "655e70100000000000000001"},
  "environment": "builder",
  "runtime_ref": "dev-runtime",
  "system_id": "7b38858b-6f26-4647-9dfb-84044000413a",
  "schema_version": 1,
  "state_version": {"$numberLong": "7"},
  "desired_pipelines": {
    "ingestion": {"state": "online", "config_revision": "rev-003", "confirmed_at": {"$date": "2026-11-19T02:00:00Z"}},
    "inference": {"state": "unloaded", "config_revision": null, "confirmed_at": {"$date": "2026-11-19T02:04:00Z"}}
  },
  "pending_operation": null,
  "last_observation": {
    "state": "loaded",
    "observed_at": {"$date": "2026-11-19T02:05:00Z"},
    "system_status": {
      "system_id": "7b38858b-6f26-4647-9dfb-84044000413a",
      "active_config_revision": "rev-003",
      "loaded": true,
      "busy": false,
      "index_ready": true,
      "index_generation": "40925e4c-56ba-4092-a019-69391d558b01",
      "can_ingest": true,
      "can_query": false,
      "pipelines": {
        "ingestion": {"loaded": true, "ready": true, "config_revision": "rev-003", "index_generation": "40925e4c-56ba-4092-a019-69391d558b01"},
        "inference": {"loaded": false, "ready": false, "config_revision": null, "index_generation": null}
      }
    }
  },
  "last_confirmed_index_generation": "40925e4c-56ba-4092-a019-69391d558b01",
  "created_at": {"$date": "2026-11-19T01:55:00Z"},
  "updated_at": {"$date": "2026-11-19T02:05:00Z"}
}
```
