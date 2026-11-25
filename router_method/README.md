# Retrieval Router MVP

此 MVP 包含 Provider 上架、User 建立 System，以及透過 Route Service 實際呼叫 Provider 的流程。

- [Config Schema Meta Schema](config-schema.meta.schema.json)
- [Provider 與 User 流程圖](architecture.md)
- [示範 Provider 的 System Description](demo-provider.json)
- [Mock Retrieval Service 預設範本](mock-provider.json)

## 啟動

在 repo 根目錄執行：

```sh
python -m pip install -r router_method/requirements.txt
python router_method/server.py
```

開啟 [http://127.0.0.1:8765](http://127.0.0.1:8765)。可用 `--port` 指定其他埠。

1. 切到 **Provider**，按 **Provide Retrieval System Template**。表單預填三支 API、Auth、Ingestion／Inference 說明與 JSON Sample，以及 Config Schema，並提供 User 表單預覽。上架後可在 Template 圖卡選 **Edit Template**。Provider 頁與編輯表單的 **使用說明** 會開啟 [Provider 使用說明書](http://127.0.0.1:8765/provider-guide)，包含設定欄位、API 契約與排查方式。
2. 切到 **User**，從左側選擇 Workspace，再按 **Create Retrieval System**。選擇已上架的 Provider Template 並填寫參數。Builder 呼叫 Init，收到 `200` 或 `204` 後將 System 顯示在該 Workspace 的圖卡清單。
3. 在 System 圖卡按 **Ingest** 或 **Inference**，使用預填的 Sample 或編輯 JSON Body，輸入呼叫端的 Auth Header 值後送出。內建示範的兩個操作都使用 `Bearer demo-token`。
4. Route Service 依 System 和操作取已登錄的 URL，送出 `{system_id, parameters, payload}` 並轉發 Auth。Response 區保留 Provider 的 Body 與狀態碼。Init 的 `payload` 為 `null`。
5. **Edit Config** 以相同 System ID 重新呼叫 Init，成功後才套用設定。**Export YAML** 下載已啟用的 Router 設定、參數與 API 綁定，Init Auth 保留環境變數引用。

Provider Templates 是跨 Workspace 共用的目錄。調整 Template 後，新建的 System 使用最新內容。既有 System 保留建立時的 API 與 Schema。

## 用獨立 Mock Service 建立 System

Router 啟動時會自動上架 **Mock Retrieval Service** 範本。使用前，在另一個終端啟動 Mock Service 並保持運作。

```sh
python router_method/mock_retrieval_service.py
```

在 Router 的 **User → Create Retrieval System** 選擇 **Mock Retrieval Service**、輸入 System 名稱，再按 **建立並初始化**。建立後可從圖卡直接使用預填的 JSON Sample 測試 Ingest 和 Inference。此範本不需 Auth 或額外設定。

| API | Response 的 `message` 欄位（HTTP 200，JSON） |
|---|---|
| `POST http://127.0.0.1:8766/init` | `成功呼叫init` |
| `POST http://127.0.0.1:8766/ingestion` | `成功呼叫ingestion` |
| `POST http://127.0.0.1:8766/inference` | `成功呼叫inference` |

Mock 的 `"see payload"` 回傳收到的完整 JSON Body。從 Router 呼叫時，這裡會看到 `system_id`、`parameters` 及巢狀的 `payload`。操作頁的 **送往 Router 的 Request** 則顯示瀏覽器送出的 HTTP 方法、路徑、Body 和遮蔽後的 Auth，方便對照兩段請求。若以 `--port` 改用其他埠，先在 Provider 圖卡編輯範本的三個 URL，再建立 System。

## Meta Schema 支援範圍

| 位置 | 允許的欄位 |
|---|---|
| 根層 | `type: "object"`、`properties`、`required`、`title`、`description`、選填的 Draft 2020-12 `$schema` 與 `additionalProperties: false` |
| 單一參數 | `type`、`title`、`description`、`default`、`enum` |
| 參數型別 | `string`、`integer`、`number`、`boolean` |

有 `enum` 時顯示下拉選單，其餘依型別顯示輸入欄。Builder 同時檢查 `required` 指向已宣告參數，以及 `default` 符合欄位設定。啟動參數驗證採已宣告欄位。

## Auth 與資料

- 內建 Provider 的 Init Auth 已預填，後端會在呼叫內建 Init 端點時帶入示範憑證。接自己的 Provider 時，可填 Header 名稱和環境變數名稱，並在啟動後端前設定該變數。
- Ingestion／Inference 的 Auth 欄位宣告須帶的 Header 與選填格式提示。User 輸入完整 Header 值，Route Service 依原值轉發。
- MVP 資料保存在服務程序記憶體，重新啟動會恢復示範資料。Provider 上架 URL 和使用者存取由本機操作人員管理。
