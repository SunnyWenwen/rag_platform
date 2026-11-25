# Retrieval Router Prototype

此原型包含 Provider 上架、User 建立 System，以及透過 Route Service 實際呼叫 Provider 的流程。

- [Config Schema Meta Schema](config-schema.meta.schema.json)
- [Provider 與 User 流程圖](architecture.md)
- [示範 Provider 的 System Description](demo-provider.json)

## 啟動

在 repo 根目錄執行：

```sh
python -m pip install -r router_method/requirements.txt
python router_method/server.py
```

開啟 [http://127.0.0.1:8765](http://127.0.0.1:8765)。可用 `--port` 指定其他埠。

1. 在 **Provider page** 填寫 System 名稱、三支 API 的 URL 和 Auth。Ingestion／Inference 各填一段使用說明與一筆 JSON Sample。貼上 Config Schema 後，右側顯示 User 建立時的表單。
2. 在 **User page** 選擇已上架的 Provider，填寫參數並建立 System。Builder 呼叫 Init，收到 `200` 或 `204` 後啟用 System。
3. 開啟 **Ingestion** 或 **Inference**，使用預填的 Sample 或編輯 JSON Body，輸入呼叫端的 Auth Header 值後送出。內建示範的兩個操作都使用 `Bearer demo-token`。
4. Route Service 依 System 和操作取已登錄的 URL，送出 `{system_id, parameters, payload}` 並轉發 Auth。Response 區保留 Provider 的 Body 與狀態碼。Init 的 `payload` 為 `null`。

## Meta Schema 支援範圍

| 位置 | 允許的欄位 |
|---|---|
| 根層 | `type: "object"`、`properties`、`required`、`title`、`description`、選填的 Draft 2020-12 `$schema` 與 `additionalProperties: false` |
| 單一參數 | `type`、`title`、`description`、`default`、`enum` |
| 參數型別 | `string`、`integer`、`number`、`boolean` |

有 `enum` 時顯示下拉選單，其餘依型別顯示輸入欄。Builder 同時檢查 `required` 指向已宣告參數，以及 `default` 符合欄位設定。啟動參數驗證採已宣告欄位。

## Auth 與資料

- Init 的 Auth 選填 Header 名稱和環境變數名稱。設定變數後再啟動原型，發送時才會讀取憑證。
- Ingestion／Inference 的 Auth 欄位宣告須帶的 Header 與選填格式提示。User 輸入完整 Header 值，Route Service 依原值轉發。
- 原型資料保存在服務程序記憶體，重新啟動會恢復示範資料。Provider 上架 URL 和使用者存取由本機操作人員管理。
