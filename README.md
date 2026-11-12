# Retrieval Builder／Retrieval Engine

User 在 Builder 設定、測試及匯出 Retrieval System。System 由 Retrieval Engine Library、有效 Config 與環境綁定組成。User 可選用內建方法或直接設定外部 Remote API。Admin 以版本化設定檔維護全域模板，Builder 提供「選用模板」。

| 手冊 | 主責 |
|---|---|
| [01 架構、名詞與責任](docs/01_architecture.md) | User／Admin、Workspace／System、共用與獨立 Runtime |
| [02 共用資料契約](docs/02_data_contracts.md) | Document、有效欄位、QueryContext[]、IndexBinding |
| [03 Engine 與模組](docs/03_engine_and_components.md) | 模組執行、Remote API 及替換範圍 |
| [04 Schema 推導](docs/04_component_descriptor.md) | 內建描述、上下游相依與 Remote 契約產生 |
| [05 System Config](docs/05_system_config.md) | 參數、有效設定、模板版本與變更影響 |
| [06 Runtime API 與部署](docs/06_runtime_api_and_deployment.md) | 批次 Ingestion、Inference、文件工作、部署與認證 |
| [07 Builder UI](docs/07_builder_ui.md) | 表單、模板選用、測試操作及 Backlog |
| [08 開發計畫與決策](docs/08_plan_and_decisions.md) | 最新決策、里程碑、未決事項與驗收 |

- 接外部服務依序看 [03 Remote API](docs/03_engine_and_components.md#remote-api)、[05 設定](docs/05_system_config.md)及[契約範例](examples/user_remote_api/README.md)。
- [01_ui_prototype.html](01_ui_prototype.html) 可離線操作，展示有效契約、套用模板及批次 Request。真實服務、模型和索引由 Runtime 實作。
- [Schemas](schemas/README.md) 區分現行契約與歷史測資。舊規格與驗證入口見[歷史索引](docs/history/superseded/2026-11-11_developer_mode.md)。
- 圖面：[User 流程](diagrams/01_user_system_l1.png)、[Infra](diagrams/02_infra_architecture.png)、[模組與 System](diagrams/03_module_component_concept.png)。
