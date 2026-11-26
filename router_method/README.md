# Retrieval Builder MVP

Builder 提供 Provider Template 上架、Workspace 內的 Retrieval System 管理，以及 Ingestion／Inference 測試。Provider 負責每個 System 的設定、認證、資源與資料生命週期。呼叫端可直接使用 Provider API，執行時只需帶 `system_id`、業務 `payload` 及 Provider 要求的 Auth。

- [Provider 與 User 流程圖](architecture.md)
- [Provider 使用說明書](provider-guide.html)
- [Config Schema Meta Schema](config-schema.meta.schema.json)
- [示範 Provider System Description](demo-provider.json)
- [Mock Provider 範本](mock-provider.json)

## 啟動

從 repo 根目錄執行。Builder 建置前端需要 Node.js 與 npm。

```sh
python -m pip install -r router_method/requirements.txt
python router_method/server.py
```

開啟 [http://127.0.0.1:8765](http://127.0.0.1:8765)。Python 啟動入口會建置 React 並提供前端與管理 API。已建置 `dist/app.js` 時可加 `--skip-build`。接入自己的 Provider 時，請先啟動該服務並確認 Builder 後端能連到其 URL。

## 上架與使用

1. 在 **Provider → Provide Retrieval System Template** 填寫 System 名稱、三支 API 的 URL 與 Auth、Ingestion／Inference 說明與 JSON Sample，以及 Config Schema。右側會預覽 User 表單。可從 Provider 頁開啟使用說明書。
2. 在 **User → Create Retrieval System** 選 Workspace 與範本、填寫設定。Builder 分配 `system_id`，直接向 Provider 的 Init API 送出 `{system_id, parameters}`。Provider 回 `200` 或 `204` 後，Builder 才顯示已啟用的 System。
3. 在圖卡按 **Ingest** 或 **Inference**，編輯預填的 Sample，並視需要輸入完整 Auth Header 值。Builder 後端補上 `system_id`，以 `{system_id, payload}` 呼叫 Provider。Response 區呈現 Provider 的 HTTP 狀態碼及 Body。內建示範的業務憑證為 `Bearer demo-token`。
4. **Edit Config** 用原本的 `system_id` 重新呼叫 Init，Provider 成功套用後 Builder 才更新畫面上的設定。Init 明確失敗時，Builder 顯示錯誤並保留最後確認成功的設定，Provider 應保留對應的生效設定和資源。若 Builder 沒收到 Init 結果，畫面提供重試，沿用同一個 ID 與設定。
5. **Export YAML** 下載直連資訊，包含 System ID 及兩支業務 API 的 URL、Auth 提示、說明和 Sample。呼叫端可使用已完成初始化的 Provider，或從操作頁複製直連 Provider 的 cURL。Auth 值在畫面及 cURL 中會遮蔽，重送時請填入真實值。

Provider Template 在 Workspace 間共用。調整 Template 後，新建的 System 使用最新內容，既有 System 沿用建立時的 API 與 Schema。匯出 YAML 用於呼叫已初始化的 System。Provider 自行管理服務部署及資源初始化。

## Provider API 契約

| API | Method 與 JSON Body | Provider 職責 |
|---|---|---|
| Init | `POST {system_id, parameters}` | 建立或更新設定與所需資源。設定可用時才回 `200` 或 `204`。 |
| Ingestion | `POST {system_id, payload}` | 依 System ID 取得已生效設定並處理 Provider 定義的資料操作。 |
| Inference | `POST {system_id, payload}` | 依 System ID 取得已生效設定並執行查詢。 |

三支 API 都使用 `Content-Type: application/json`。由 Provider 驗證業務憑證有權操作指定的 `system_id`。已收到的 Provider 業務回應在測試頁標示為 `provider`，由 Builder 產生的輸入驗證、System 查找或上游連線錯誤則標示為 `builder`。測試頁使用的 Header 為 `Retrieval-Response-Source`。

Init 的 `secret_ref` 指向 **Builder 程序**的環境變數，值包含完整 Header 內容。內建示範提供自己的 Init 憑證。業務 Auth 由呼叫端提供，測試頁只傳送範本指定的 Auth Header。既有服務如果要把設定放進每次內部呼叫，由 Provider 在自己的介面層轉換。

## 用獨立 Mock Provider 測試

Builder 啟動時會載入 **Mock Retrieval Service** 範本。另開終端啟動 Mock。

```sh
python router_method/mock_retrieval_service.py
```

接著在 **User → Create Retrieval System** 選 Mock 範本。本機 Mock 不需 Auth 或額外設定。若改用其他埠，先更新範本的三個 URL，再建立 System。

| API | HTTP 200 的 `message` |
|---|---|
| `POST http://127.0.0.1:8766/init` | `成功呼叫init` |
| `POST http://127.0.0.1:8766/ingestion` | `成功呼叫ingestion` |
| `POST http://127.0.0.1:8766/inference` | `成功呼叫inference` |

Mock 的 `"see payload"` 會回傳收到的完整 JSON Body。操作頁的 **Provider Request** 可與此欄位對照。展開 **瀏覽器送往 Builder 的測試 Request** 可看到只包含業務 Payload 的瀏覽器請求。Mock 重啟後須重新 Init，已建立的 System 可透過 **Edit Config** 重新套用。

## Meta Schema 支援範圍

| 位置 | 允許的欄位 |
|---|---|
| 根層 | `type: "object"`、`properties`、`required`、`title`、`description`、選填的 Draft 2020-12 `$schema` 與 `additionalProperties: false` |
| 單一參數 | `type`、`title`、`description`、`default`、`enum` |
| 參數型別 | `string`、`integer`、`number`、`boolean` |

`enum` 顯示為下拉選單。Builder 會驗證必填欄位、預設值及送出的設定。Builder、內建示範和 Mock 皆為本機 MVP，執行狀態保存在各自的程序記憶體。
