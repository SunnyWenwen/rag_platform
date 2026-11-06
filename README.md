# Retrieval Builder／Retrieval Engine

以設定組合可擴充的檢索流程，提供 Builder 測試與匯出後的獨立 Runtime。核心關係為 **Retrieval Engine Library＋Config＋資源綁定 → Retrieval System**。

## 現行文件：八份主題手冊

| 順序 | 文件 | 唯一主責內容 |
|---|---|---|
| 1 | [架構、名詞與責任](docs/01_architecture.md) | 產品邊界、A～E 大盤、角色、Builder DEV／FTEST／ENT、圖面解讀 |
| 2 | [共用資料契約](docs/02_data_contracts.md) | IngestionDocument／ParsedDocument／Chunk／QueryContext[]／IndexBinding、語意、Python 連續範例 |
| 3 | [Engine 與 Component 開發](docs/03_engine_and_components.md) | Module 方法、共用 Flow／Context、SDK／Registry、Local／Remote 開發與交付 |
| 4 | [Component Descriptor](docs/04_component_descriptor.md) | 已確認細化行為、Config／Data Schema、動態選項／UI、候選格式與 DS-01～DS-13 |
| 5 | [System Config](docs/05_system_config.md) | 版本、草稿／有效設定、變更影響、D 草案與 SC-01～SC-10 |
| 6 | [Runtime API 與部署](docs/06_runtime_api_and_deployment.md) | 九支 API、Queue／工作狀態、14 項 Runtime 控制、Remote／Export／環境綁定 |
| 7 | [Builder UI 與 Backlog](docs/07_builder_ui.md) | 目標互動、v0.12 模擬現況、40 個未勾選工作項；UIB 重號已整理 |
| 8 | [開發計畫、決策與驗收](docs/08_plan_and_decisions.md) | 已確認基線、M0～M7、Q-001～Q-028、狀態與驗收；其他決策表只連回主責文件 |

## 依工作選擇閱讀順序

- 介紹／報告：1 → 相關圖面 → 7 的原型現況。
- 目前的規格討論：4 的 DS 候選 → 5 的 SC 候選 → 8 的其餘 Q；候選不因整理文件而核定。
- Local Developer：1 的 A～E → 2 的相關資料邊界 → 3 的 SDK／交付 → 4 的描述規格。
- Remote Developer：2 的公開邊界 → 3 的 Manifest／Adapter → 4 的共同描述 → 6 的 Image／External 部署。
- Builder／平台開發：1 → 4／5 → 6 → 7 → 8。

## 現況與不可混用的邊界

- Retrieval-only，沒有 Generation；Rewrite／AI 助手仍可用 LLM，Evaluation 保留 M6。
- Parser 正規化為平面 units；Chunker 不跨 Unit 合併／overlap。追溯 _rag 選用，metadata 提示由 Component 明確支援。
- Builder 共用 API／Flow，每次請求固定 Config；FTEST／ENT 初期單一 System 配置。同 System Ingestion 結束後才允許新版生效。
- 新 Descriptor 的具體語法與 System Config 尚未定案；取消獨立 document_schema，業務欄位由 Component 宣告＋Config 提供。
- 原型、離線 Schema／樣本驗證、真實服務實作分開看。這次整合不修改 UI 或執行演算法。

## 程式、Schema 與展示入口

| 資產 | 入口 |
|---|---|
| 共用機器 Schema | [schemas/](schemas/)；欄位語意以資料契約手冊為準 |
| Descriptor 候選與五組對照 | [examples/component_descriptor](examples/component_descriptor/README.md)；含離線驗證與限制 |
| Python 型別／連續範例 | [models.py](examples/pydantic_contracts/models.py)、[typed_examples.py](examples/pydantic_contracts/typed_examples.py) |
| Parser Local／Remote 教學 | [examples/component_development](examples/component_development/)；開發步驟見 Engine 手冊 |
| 瀏覽器原型 | [01_ui_prototype.html](01_ui_prototype.html)；v0.12 記憶體模擬，正式差異見 UI 手冊 |
| L1 使用／開發流程 | [PNG](diagrams/01_user_system_l1.png)／[MMD](diagrams/01_user_system_l1.mmd)／[SVG](diagrams/01_user_system_l1.svg) |
| Infra | [PNG](diagrams/02_infra_architecture.png)／[MMD](diagrams/02_infra_architecture.mmd) |
| Module／Component／三個 System | [圖說](diagrams/03_module_component_concept.md)／[PNG](diagrams/03_module_component_concept.png)／[MMD](diagrams/03_module_component_concept.mmd) |
| 三種交付模式 | [圖說](diagrams/04_component_delivery_modes.md)／[PNG](diagrams/04_component_delivery_modes.png) |

## 文件維護與歷史查驗

每個議題只更新主責手冊，其他手冊引用。M0～M7／Q 不因文字搬移而改狀態；DS／SC／API-D 保留主責表，UI 只在明確要求時修改。Runtime 與 Builder 仍規劃為 rag_engine／rag_platform 兩個 repo，本次沒有建立或搬遷產品 repo。

過時草案、原始決策、一次性證據與討論過程放 [history/](docs/history/README.md)。本次整合前的 23 份規格與 README 均保留來源版本快照，完整對照見 [整合紀錄](docs/history/changes/2026-11-05_documentation_consolidation.md)。
