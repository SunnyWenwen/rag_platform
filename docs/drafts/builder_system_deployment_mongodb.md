# Builder System 部署狀態與 MongoDB Collection 草案

Builder 保存 System、所有 Config Revision 及各目標 Runtime 的部署意圖，並[主動管理 DEV Runtime](../06_runtime_api_and_deployment.md#builder-managed-dev-runtimes)的發布與重啟後補載。DEV 首版每個 Runtime 以一個 Pod 執行，在記憶體中持有已載入的 Config、執行物件與本地 Queue。ES 保存受管索引及控制紀錄，供 Runtime 核對索引與協調工作。獨立部署由匯出的 Config 啟動。

## Collection 欄位

Collection 名稱為 `builder_system_deployments`。每個 `(environment, runtime_ref, system_id)` 一筆，唯一鍵由三欄組成。環境與 Runtime 識別取自 Builder 選定的部署目標。同一目標的 Runtime 重啟或更換 Pod 時沿用 `runtime_ref`。完整 Config 依 `system_id` 與 `config_revision` 從 Builder 的 Config Revision 紀錄讀取。單純儲存或驗證草稿不建立部署紀錄。

即使多個 Runtime 使用同一份 Config 和同一個受管 ES 索引，Builder 仍逐目標保存部署狀態。Runtime 依 System 與索引綁定共用 [ES 控制紀錄](../06_runtime_api_and_deployment.md#ingestion-job-records)。共用索引的加入、單目標卸載及整體刪除見 [Q-020](../08_plan_and_decisions.md#q-020)。

| 欄位 | BSON 型別 | 定義 |
|---|---|---|
| `_id` | ObjectId | MongoDB Document ID。 |
| `environment`、`runtime_ref`、`system_id` | String | 環境、Runtime 部署目標及 Builder 配發的 System 識別。 |
| `schema_version` | Int32 | Document 格式版本，初版為 `1`。 |
| `state_version` | Int64 | Builder 條件更新的版本，初始為 `0`，成功更新時加一。避免較舊的同步結果覆寫新的操作。 |
| `desired` | Object / Null | 最後確認的部署意圖，含 `state`、`config_revision`、`confirmed_at`。希望上線時使用 `online` 和生效版本，已確認卸載時使用 `unloaded` 和 `null`。第一次部署尚未確認時為 `null`。 |
| `pending_operation` | Object / Null | 已發起且尚無確認結果的操作，含 `operation_id`、`kind`、`target_config_revision`、`expected_active_revision`、`expected_index_generation`、`apply_context`、`allow_rebuild`、`started_at`。操作種類為 `initialize`、`reload`、`update`、`recover_index`、`detach` 或 `unload`。`detach` 是單目標卸載；`unload` 對應 DELETE。兩者的目標 Config 版本均為 `null`。`recover_index` 的預期索引世代為已遺失的舊世代，目標版本是原發布版本。`allow_rebuild` 只在已確認重建的 `update` 使用 `true`。無待確認操作時為 `null`。 |
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

## 發布與同步

1. Builder 先保存欲發布或恢復的不可變 Config Revision 與 `pending_operation`，再以 `operation_id` 作為 `Idempotency-Key` 送出 Runtime 管理請求。收到明確成功後，以一次條件更新提交該操作適用的欄位並清除該筆操作。`initialize`、`update`、`detach`、`unload` 更新 `desired`；`detach` 只更新目標部署並保留索引世代。`reload` 與 `recover_index` 沿用 Config Revision。重啟後補載時保留原部署意圖；明確將已卸載目標再次部署時，`reload` 成功後將目標設回 `online`。索引恢復後記下新世代並安排重新匯入。
2. Builder 在**自身啟動**或**偵測到 Runtime 重連**時，逐目標核對預期上線的 System 和待確認的操作。發現目標尚未載入時，依第 4 項查核索引，再向原 `runtime_ref` 的管理入口下發已發布的 Config。草稿及已確認卸載且無待處理操作的 System 無須重新載入。
3. 逾時或中斷時保留待確認操作。以 Runtime 狀態與該操作的結果補記成功。恢復前後版本相同，確認成功還須比對索引世代已更新且就緒。卸載前以單一 System GET 取得預期版本與索引世代。單目標 `detach` 待確認期間暫停該目標補載，以 `detach` 結果確認卸載。共用索引若正在刪除，Builder 在待確認期間暫停相關目標的補載與索引恢復，以 DELETE 的結果確認清除後更新受影響的部署狀態。明確失敗後可清除該次待處理操作並保留原部署意圖。
4. 沒有待確認操作且 System 預期上線時，載入狀態不明、查無載入或索引未就緒，可由 Builder 取已發布版本請 Runtime 預檢。原索引相容且尚未載入時走 `reload`。確認索引遺失時，Builder 回報異常並保留 `desired` 和最後確認世代。使用者確認重建後，才保存 `pending_operation` 並以原 Config Revision 和最後確認世代發起 `recover_index`。新世代就緒後，Builder 向仍預期上線的其他共用目標下發 `reload`，並依[初次匯入規則](../07_builder_ui.md#builder-initial-ingestion-readiness)安排重新匯入。
5. Runtime 回報 Builder 無法對應的生效版本時，保留版本差異供查核。Runtime 無法連線時保留 `desired` 及 `pending_operation`。原請求以同一操作鍵查核；需要重新發起操作時先確認原操作已結束，再重驗 Config 與索引影響。新出現的破壞性影響須另行確認。

`desired` 是 Builder 用來重啟後重新載入的目標，`last_observation` 記錄目標 Runtime 最近一次查詢的結果。Runtime 依實際載入的快照和索引狀態回報即時能力。操作前置條件、恢復流程及重送語意見 [System 生命週期 API](../06_runtime_api_and_deployment.md#system-lifecycle-api)。

## 已發布的紀錄範例

以下使用 MongoDB Extended JSON 表示 BSON 值。

```json
{
  "_id": {"$oid": "655e70100000000000000001"},
  "environment": "dev",
  "runtime_ref": "dev-runtime",
  "system_id": "crm-search",
  "schema_version": 1,
  "state_version": {"$numberLong": "7"},
  "desired": {
    "state": "online",
    "config_revision": "rev-003",
    "confirmed_at": {"$date": "2026-11-19T02:00:00Z"}
  },
  "pending_operation": null,
  "last_observation": {
    "state": "loaded",
    "observed_at": {"$date": "2026-11-19T02:05:00Z"},
    "system_status": {
      "system_id": "crm-search",
      "active_config_revision": "rev-003",
      "loaded": true,
      "busy": false,
      "index_ready": true,
      "index_generation": "g0001",
      "can_ingest": true,
      "can_query": true
    }
  },
  "last_confirmed_index_generation": "g0001",
  "created_at": {"$date": "2026-11-19T01:55:00Z"},
  "updated_at": {"$date": "2026-11-19T02:05:00Z"}
}
```
