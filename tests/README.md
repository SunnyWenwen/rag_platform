# 驗證入口

## 現行契約

在 repo 根目錄執行以下離線驗證。需要 Python 3.10 以上、`jsonschema` 4.x 和 `referencing`。

```sh
python3 examples/system_config/validate_descriptor_draft.py
python3 examples/system_config/validate_runtime_http_examples.py
python3 examples/user_remote_api/validate.py
```

三支腳本分別驗證 System Config／Descriptor／Catalog、Runtime HTTP 範例及其跨步驟關聯，以及共用 Document 與 Remote API。DEV Runtime 的實際 HTTP、部署與搜尋由整合測試驗收。

## UI prototype 回歸

瀏覽器回歸涵蓋草稿保存、無效選值、索引發布、CSV 映射、Run 狀態、Filter、索引沿用／重建及窄版畫面。在 repo 根目錄用已安裝 Playwright 和 Chromium 的 Node.js 環境執行。

```sh
node tests/w1-prototype.browser.test.cjs
```

可用 `CHROMIUM_EXECUTABLE` 指定 Chromium。舊版的九支測試和對應 HTML 一起保留在[舊 Prototype 快照](../docs/history/source_snapshots/ui-prototype-v015/)。
