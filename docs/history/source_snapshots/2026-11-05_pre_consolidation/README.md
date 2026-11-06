> 歷史來源快照：README.md；來源 commit 916734ac0bbe0631a205bfd52626ce332aa7beb2。2026-11-05 整合後不再作現行規格；相對連結固定到來源版本。現行入口：[README](https://github.com/SunnyWenwen/rag_platform/blob/docs/rag-system-factory/README.md)。

# Retrieval Builder

以 Config 建立、測試及交付 Retrieval System。Builder 提供設定、資料上傳轉換、檢索查詢與評估介面；獨立部署的 Runtime 提供 API，使用相同 Engine 與邏輯 Config。

目前為開發規格、契約驗證範例與模擬 UI，尚未完成可部署的 Engine／Runtime。文件同步日期：2026-11-05。需求先更新文件，UI 差異記入 [Backlog](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/10_ui_adjustment_backlog.md#ui-backlog-pending)，收到改 UI 指示後才實作。

## 契約與責任總盤點

先讀 [20 契約、設定與責任總盤點](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/20_contract_inventory_responsibility_matrix.md)：以 A～E 整理 Admin／Developer／User 責任、Developer 要讀與要交付的內容，以及 Library／Builder／Deploy 的直接用途。本文中的 Builder DEV 是 Retrieval Builder 提供的開發／測試環境；FTEST／ENT 是使用單位的目標部署環境，三者沿用相容的邏輯 Config、分別提供環境綁定。Descriptor／Manifest／動態 UI 的具體格式仍有待定項。

## 三份共用資料契約

資料順序為 **IngestionDocument → ParsedDocument → Chunk**；Embedding 擴充同一個 Chunk 的 vectors，Indexing 保存完整內容，Inference 的 ResultItem 引用同一份 Chunk 定義。

| 契約 | 交接邊界 | 定義與例子 |
|---|---|---|
| IngestionDocument | API List 的每個 item／Import／Parser 共用輸入；document_id＋content／base64／uri 三選一 | [13 說明](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/13_ingestion_parser_input_contract.md) · [Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/ingestion_document.schema.json) · [分類案例](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/contracts/report_cases.json) |
| ParsedDocument | Parser 輸出／Chunker 輸入；document_id、source_revision、units、metadata | [14 說明](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/14_parsed_document_contract.md) · [Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/parsed_document.schema.json) · [案例](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/plain_text.json) |
| Chunk | Chunking 後的下游資料；chunk_id、document_id、source_revision、fields、metadata、vectors | [15 說明](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md) · [Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/chunk.schema.json) · [案例](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/chunk/cases.json) |

JSON Schema 定義物件形狀，13～15 定義語意與相容規則，參考驗證器檢查跨欄位關係。Parser 統一輸出平面 Units；Chunker 仍需符合所選欄位／文字格式／Tokenizer 條件。已確認方向作為開發依據；各草案的正式版本／SDK、索引提交與更新政策仍由 [08 的 Q-ID](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-002) 追蹤。

Chunk 預設逐 Unit 切 units[i].text 並寫入 fields.text；進階多欄位任務各自切分、串接結果，2＋3 得 5 個 Chunk。每個任務預設輸出 text；完整原文只在明確 copy 時附帶，使用不衝突名稱。metadata 全部有效繼承；D-52 下 _rag／來源位置／fingerprint／ordinal 為 Component 選填，有提供才驗證。metadata 也可傳遞 Component 支援的處理提示，例如 chunking_mode=passthrough，不新增全域規則引擎。Embedding 預設 fields.text → vectors.text，每個向量保存 values／embedding_profile_id／source_field。

## 推論 Contract 與本輪 UI

推論直接傳 **QueryContext[]**：ori_query、query、filters、result_sets、metadata；ResultSet=key/items，ResultItem=chunk/選填score。只保留目前有效資料，名次由 items 順序表示；RRF 用位置，Sum Score 仍需完整可比分數。舊 InferenceState wrapper 明確停用。定義與例子見 [05](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/05_data_contracts_search_design.md#query-context-contract)、[17](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/17_pydantic_contracts_draft.md)、[Inference Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/inference_context.schema.json)。

Prototype v0.12 同步 Query metadata、選填追溯、Embedding 文字模板／衍生欄位選取、獨立原文 Chunk，以及 Developer Local／Remote Image／External 的模擬目錄、動態表單、整段鎖定與匯出差異。真實 Runtime／Registry／AI／模型／部署尚未串接；完成範圍及未核定提案見 [10](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/10_ui_adjustment_backlog.md)。

## 文件導覽

| 文件 | 責任 |
|---|---|
| [03 系統概覽與架構](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/03_architecture_proposal.md) | 正式名詞、角色、架構、兩個 repo 與部署邊界 |
| [04 Engine 與模組 I/O](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/04_module_components_io_contracts.md) | Pipeline、Module 行為、Component 載入與執行 |
| [05 資料與 Config](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/05_data_contracts_search_design.md) | 契約總覽、Inference 物件、設定責任與變更影響 |
| [06 UI 開發規格](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/06_ui_development_spec.md) | Create／Edit、欄位相依、CSV、預覽及助手 |
| [07 Backend 與 Runtime API](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/07_backend_runtime_integration.md) | JSON API、工作狀態、儲存、服務綁定與 Export |
| [08 開發計畫與決策](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md) | M0～M7、現行決策摘要、Q-001～Q-028 與驗收 |
| [09 Inference Contract 與 UI](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/09_inference_contract_ui_plan.md) | ResultSet、兩層融合、四處 Top N 與連動 |
| [10 UI Backlog](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/10_ui_adjustment_backlog.md) | 現有原型能力及UIB-001～023 的原型／正式整合狀態 |
| [11 Component 開發指南](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/11_component_developer_guide.md) | SDK 示意、開發、契約測試、PR 與發布 |
| [12 Component 設定描述](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/12_component_schema_ui_contract.md) | Config Schema、UI hints、動態選項與相依規則 |
| [13 IngestionDocument](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/13_ingestion_parser_input_contract.md) | 輸入分類、路由、API／Parser 相同 Schema |
| [14 ParsedDocument](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/14_parsed_document_contract.md) | 平面 Units、Parser／Chunker 分工與來源追溯 |
| [15 Chunk](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md) | 切分／複製、來源、向量、ID 與欄位組裝待討論 |
| [16 Parser 開發範例](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/16_parser_component_development_examples.md) | 共用 Pydantic、Local ABC、Remote Adapter 與 FastAPI，搭配三種交付模式圖 |
| [17 Pydantic Contract 草案](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/17_pydantic_contracts_draft.md) | 03 圖中共用資料物件、推論型別、已確認的輕量 IndexBinding、可執行模型與 JSON Schema 目錄 |
| [18 Remote Service／Pipeline 整合](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/18_remote_service_pipeline_integration.md) | Manifest 註冊、連續 Module 替換、三種部署、固定服務與 Export／UI 卡控 |
| [19 IndexBinding／Artifact 契約](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/19_index_binding_artifact_contract.md) | 單組邏輯索引、Binding 五鍵、索引格式定義與相容性 |
| [20 契約與責任總盤點](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/20_contract_inventory_responsibility_matrix.md) | A～E 詳細總表、角色／系統分工、Developer 交付、Builder DEV 與 FTEST／ENT 邊界 |
| [21 Runtime API 盤點](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/21_runtime_ingestion_inference_api_inventory.md) | Ingestion／Inference、文件存在／ID 清單／retire、202／工作狀態、錯誤格式與可信 System 路由 |
| [22 Runtime 可調參數](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/22_runtime_settings_catalog.md) | 已確認的 Runtime 限制預設、作用範圍與管理者；文件摘要／分頁參數分開記錄 |
| [23 System Config 初版](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/23_system_config_schema_draft.md) | D-67 後共同骨架與 SC-01～SC-10；原五案例／機器稿保留歷史對照 |
| [24 Component I/O 細化](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/24_component_io_schema_refinement.md) | B 的資料規格、六類純宣告、逐層選項／相依及驗收；取消獨立 document_schema |
| [25 Descriptor Schema 初版](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/25_component_descriptor_schema_draft.md) | 具體包裝／規則、五組對照範例與 DS-01～DS-13 決策建議；格式未核定 |
| [歷史資料夾](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/history/README.md) | 過時規格、決策演變、更新流水帳、校對及驗證紀錄 |

名詞以 03 為準；資料的精確定義引用 schemas/ 與 13～15，不在各模組重寫一份。Component Developer 先由 20 選擇 Local／Remote 閱讀路線，再依 11 → 04 → 對應資料契約 → 12／18 準備交付。完整 Engine Config／SDK 尚未凍結，示例不等於可直接執行的產品介面。

兩個目標 repo：rag_platform 管理 Builder 前後端；rag_engine 集中 SDK、Engine、Components 與 Runtime API，整合發布 Runtime Image。API／Schema 相容時，Builder 與 Runtime 可分別升級；目前尚未由此規劃建立新 repo 或搬移程式。

開發順序：M0 規格 → M1 最小 Engine → M2 Component／能力擴充 → M3 Runtime API → M4 獨立 AI 設定助手 → M5 Builder 與助手整合 → M6 Evaluation → M7 獨立部署交付。

## 原型、圖面與驗證

- [UI Prototype](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/01_ui_prototype.html)：瀏覽器模擬設定與操作；v0.12 已套用 Retrieval-only、平面 Units、Chunk 追溯與分組檢索輸出，保留 JSON／CSV、Fixed-size 及多任務映射；真實目錄／服務仍未串接，驗證範圍見 10。
- [L1 流程 PNG](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/01_user_system_l1.png) · [MMD](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/01_user_system_l1.mmd) · [SVG](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/01_user_system_l1.svg)
- [Infra PNG](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/02_infra_architecture.png) · [MMD](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/02_infra_architecture.mmd)
- [Module／Component PNG](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/03_module_component_concept.png) · [MMD](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/03_module_component_concept.mmd) · [SVG](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/diagrams/03_module_component_concept.svg)

可執行的契約範例與測試位於 examples/parsed_document、examples/chunk、examples/inference 及 examples/contracts，各自使用共用 Schema。供應者映射與實際解析的版本、測資及驗證限制見 14；資料驗證通過不代表正式 Engine、Tokenizer、模型或 DB 串接已完成。


## 歷史與查驗

過時文件與討論／更新／校對／驗證過程集中於 [docs/history](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/history/README.md)。目前有效規格與進行中的討論稿仍由本頁導覽；歷史檔案記錄來源日期／commit 及現行取代入口。
