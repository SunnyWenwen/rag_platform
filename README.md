# RAG Builder

以 Config 建立、測試及交付 RAG System。Builder 提供設定、資料上傳轉換、問答與評估介面；獨立部署的 Runtime 提供 API，使用相同 Engine 與邏輯 Config。

目前為開發規格、契約驗證範例與模擬 UI，尚未完成可部署的 Engine／Runtime。文件同步日期：2026-10-31。需求先更新文件，UI 差異記入 [Backlog](docs/10_ui_adjustment_backlog.md#ui-backlog-pending)，收到改 UI 指示後才實作。

## 三份共用資料契約

資料順序為 **IngestionDocument → ParsedDocument → Chunk**；Embedding 擴充同一個 Chunk 的 vectors，Indexing 保存完整內容，Inference 的 ResultItem 引用同一份 Chunk 定義。

| 契約 | 交接邊界 | 定義與例子 |
|---|---|---|
| IngestionDocument | API／Import／Parser 共用輸入；document_id＋content／base64／uri 三選一 | [13 說明](docs/13_ingestion_parser_input_contract.md) · [Schema](schemas/ingestion_document.schema.json) · [分類案例](examples/contracts/report_cases.json) |
| ParsedDocument | Parser 輸出／Chunker 輸入；document_id、source_revision、fields、metadata、structure | [14 說明](docs/14_parsed_document_contract.md) · [Schema](schemas/parsed_document.schema.json) · [案例](examples/parsed_document/plain_text.json) |
| Chunk | Chunking 後的下游資料；chunk_id、document_id、source_revision、fields、metadata、vectors | [15 說明](docs/15_chunk_contract.md) · [Schema](schemas/chunk.schema.json) · [案例](examples/chunk/cases.json) |

JSON Schema 定義物件形狀，13～15 定義語意與相容規則，參考驗證器檢查跨欄位關係。共用格式不代表每個 Parser／Chunker 都支援所有結構。已確認方向作為開發依據；0.1-draft 的正式版本／SDK、索引提交與更新政策仍由 [08 的 Q-ID](docs/08_implementation_plan.md#q-002) 追蹤。

Chunk 預設切 fields.text 並寫回 text；進階多欄位任務各自切分、串接結果，2＋3 得 5 個 Chunk。每個任務預設輸出 text；完整原文只在明確 copy 時附帶，使用不衝突名稱。metadata 全部有效繼承，來源與切分追溯由 Engine 管理。Embedding 預設 fields.text → vectors.text，每個向量保存 values／embedding_profile_id／source_field。

## 文件導覽

| 文件 | 責任 |
|---|---|
| [03 系統概覽與架構](03_architecture_proposal.md) | 正式名詞、角色、架構、兩個 repo 與部署邊界 |
| [04 Engine 與模組 I/O](docs/04_module_components_io_contracts.md) | Pipeline、Module 行為、Component 載入與執行 |
| [05 資料與 Config](docs/05_data_contracts_search_design.md) | 契約總覽、Inference 物件、設定責任與變更影響 |
| [06 UI 開發規格](docs/06_ui_development_spec.md) | Create／Edit、欄位相依、CSV、預覽及助手 |
| [07 Backend 與 Runtime API](docs/07_backend_runtime_integration.md) | JSON API、工作狀態、儲存、服務綁定與 Export |
| [08 開發計畫與決策](docs/08_implementation_plan.md) | M0～M7、D-01～D-48、Q-001～Q-027 與驗收 |
| [09 Inference Contract 與 UI](docs/09_inference_contract_ui_plan.md) | ResultSet、兩層融合、四處 Top N 與連動 |
| [10 UI Backlog](docs/10_ui_adjustment_backlog.md) | 現有原型能力及未實作 UIB-001～013 |
| [11 Component 開發指南](docs/11_component_developer_guide.md) | SDK 示意、開發、契約測試、PR 與發布 |
| [12 Component 設定描述](docs/12_component_schema_ui_contract.md) | Config Schema、UI hints、動態選項與相依規則 |
| [13 IngestionDocument](docs/13_ingestion_parser_input_contract.md) | 輸入分類、路由、API／Parser 相同 Schema |
| [14 ParsedDocument](docs/14_parsed_document_contract.md) | 文字／結構、位置、擴充與 Parser 相容性證據 |
| [15 Chunk](docs/15_chunk_contract.md) | 切分／複製、來源、向量、ID 與欄位組裝待討論 |

名詞以 03 為準；資料的精確定義引用 schemas/ 與 13～15，不在各模組重寫一份。Component Developer 依序讀 11 → 04 → 對應資料契約 → 12。完整 Engine Config／SDK 尚未凍結，示例不等於可直接執行的產品介面。

兩個目標 repo：rag_platform 管理 Builder 前後端；rag_engine 集中 SDK、Engine、Components 與 Runtime API，整合發布 Runtime Image。API／Schema 相容時，Builder 與 Runtime 可分別升級；目前尚未由此規劃建立新 repo 或搬移程式。

開發順序：M0 規格 → M1 最小 Engine → M2 Component／能力擴充 → M3 Runtime API → M4 獨立 AI 設定助手 → M5 Builder 與助手整合 → M6 Evaluation → M7 獨立部署交付。

## 原型、圖面與驗證

- [UI Prototype](01_ui_prototype.html)：瀏覽器模擬設定與操作；三份新資料契約的 UI 遷移記於 UIB-011～013。
- [L1 流程 PNG](diagrams/01_user_system_l1.png) · [MMD](diagrams/01_user_system_l1.mmd) · [SVG](diagrams/01_user_system_l1.svg)
- [Infra PNG](diagrams/02_infra_architecture.png) · [MMD](diagrams/02_infra_architecture.mmd)
- [Module／Component PNG](diagrams/03_module_component_concept.png) · [MMD](diagrams/03_module_component_concept.mmd) · [SVG](diagrams/03_module_component_concept.svg)

可執行的契約範例與測試位於 examples/parsed_document、examples/chunk、examples/inference 及 examples/contracts，各自使用共用 Schema。供應者映射與實際解析的版本、測資及驗證限制見 14；資料驗證通過不代表正式 Engine、Tokenizer、模型或 DB 串接已完成。

舊輸入格式、完整單層 YAML、可任意排列結果處理卡片及逐次更新流水帳已移除；歷史由 Git 保留。尚未確認的 concat／固定文字組裝、LLM 結構化輸出及正式發布政策保留為提案，不當成既定功能。
