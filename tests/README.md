# 驗證入口

## 現行契約

在 repo 根目錄執行以下離線驗證。需要 Python 3.10 以上、`jsonschema` 4.x 和 `referencing`。

```sh
python3 examples/system_config/validate_descriptor_draft.py
python3 examples/user_remote_api/validate.py
```

第一支驗證 `0.2-draft` 的 System Config、Descriptor、欄位推導、型別化 Filter 及索引相依。第二支驗證共用 Document、Ingestion、Inference 和 Remote API 測資。Runtime 的 HTTP、部署與搜尋需另做整合驗收。

## UI prototype 回歸

本目錄的九支 `.cjs` 測試直接載入 [UI prototype](../01_ui_prototype.html)，其中 `schema-contract.test.cjs` 涵蓋 Prototype 的舊欄位格式。執行時依檔案匯入安裝 jsdom 或 Playwright 等依賴。舊資料契約的離線測資見[歷史契約快照](../docs/history/superseded/legacy_contracts/README.md)。
