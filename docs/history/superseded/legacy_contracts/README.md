# 舊資料契約快照

來源為 [歸檔前的 Git 提交](https://github.com/SunnyWenwen/rag_platform/tree/9cb256673004541b9336fbcdcc03b845ee024c53)。現行資料契約與範例見 [Schemas](../../../../schemas/README.md)及[範例入口](../../../../examples/README.md)。

| 目錄 | 內容 |
|---|---|
| schemas | 舊 IngestionDocument、ParsedDocument、Chunk、InferenceContext，以及舊測資用的 IndexBinding 副本 |
| examples/parsed_document、chunk、inference | Units、Chunk.fields、ResultItem.chunk 的案例和驗證 |
| examples/component_descriptor | Descriptor 0.1 的 JSON fixtures 和離線驗證 |
| examples/component_development、pydantic_contracts | 舊 Python SDK 與資料型別示範 |
| examples/contracts | 舊規格報告的來源資料及產生器 |

各腳本使用的 `schemas/`、`examples/` 相對結構留在快照內。重跑時從本目錄進入，依各案例的 requirements 安裝依賴。[Descriptor 0.1](examples/component_descriptor/README.md)列出兩支離線驗證。舊報告產生器依賴改版前手冊的插入標記，僅保留作為歷史來源。
