# RAG Builder — 開發文件交接

> 整理日期：2026-10-15（Asia/Taipei）
>
> 規格基準：03～08 文件集 v0.12；來源提交：[a67194f](https://github.com/SunnyWenwen/rag_platform/commit/a67194fc3b3cafe0a5ecde03b3e8f407b0c0cb8f)。接續前請讀取分支最新版本。
>
> 本文件是跨對話接續入口，彙整使用者整理開發文件的目的、重要決策與尚未完成的工作。正式名詞、實作規則及決策狀態分別由 03～08 各主責文件維護，交接摘要不取代它們。

## 1. 專案與接續位置

| 項目 | 位置／現況 |
|---|---|
| Repository | [SunnyWenwen/rag_platform](https://github.com/SunnyWenwen/rag_platform) |
| 工作分支 | [docs/rag-system-factory](https://github.com/SunnyWenwen/rag_platform/tree/docs/rag-system-factory) |
| 既有 PR | [PR #1](https://github.com/SunnyWenwen/rag_platform/pull/1) |
| 本輪成果 | 重整／撰寫 03～08；核對可取得的歷史片段；統一名詞並集中於 03 §3 |
| 決策追蹤 | 08 現有 D-01～D-32、Q-001～Q-027、A-01～A-40；數量為本交接基準快照 |
| 程式現況 | HTML Prototype v0.8 與原型測試；模型、搜尋、Evaluation、API、部署仍為模擬，AI 助手尚未呼叫真實 LLM |
| 本輪工作範圍 | 開發文件與交接整理；使用者將在另一個對話繼續文件撰寫 |

使用者原本希望延續同專案的 **「技術選型」** 對話，後來發現於本對話接續。因此應保留本對話新增並已提交的決策，再與原串核對，無須重新建立一套文件。

## 2. 使用者請求整理文件的重點

1. **文件要能交給 coding agent 實際開發。**需交代責任邊界、輸入／輸出、Config、錯誤／失敗行為、依賴、完整範例與驗收方式；不能只停留在架構介紹。
2. **各文件有明確分工。**03 概覽、04 Engine、05 資料規則、06 UI、07 Backend／串接、08 開發計畫與決策。相同規則維護在主責文件，其餘引用。
3. **04＋05 要足以獨立使用 Engine。**開發者手寫 Config 並提供必要服務，就能執行 RAG；07 再將相同 Engine 包成 API，並與 Builder 串接。UI 產生 Config，由共用 Engine 執行。
4. **寫文件時同步記錄不清楚之處。**03～07 保留相關待討論清單並連回 08 的 Q-ID；08 集中維護候選、狀態、依據、影響與阻擋範圍。
5. **區分已確認、既有基線、建議／待決、後續能力。**助理提出的 Schema、框架、預設值或部署策略，沒有明確確認就維持建議；原型目前做得到的範圍也不等於產品最終需求。
6. **同時支援新手與熟悉 RAG 的使用者。**以 AI 設定助手、CSV 起始流程、基本／進階漸進呈現協助上手，並保留欄位、方法、Prompt、搜尋與受控擴充設定。
7. **維持對話決策與文件的一致性。**核對歷史時保留來源與證據限制；發現遺漏或衝突，具體列出對應章節及決策，修正主責文件。
8. **名詞集中定義。**使用者已確認將名詞併入 03 §3；05 保留對應欄位及版本規則，08 記錄決策，不另開平行的名詞權威文件。

## 3. 文件分工與閱讀順序

| 文件 | 主責內容 | 接續撰寫時的注意點 |
|---|---|---|
| [03 系統概覽與架構](../03_architecture_proposal.md) | 產品目標、正式名詞、元件關係、架構邊界、功能範圍 | [§3](../03_architecture_proposal.md#terminology) 為核心名詞定義入口；§4 保留既有流程圖／架構圖要求 |
| [04 Engine 與模組](04_module_methods_io_contracts.md) | Config 載入／驗證、Registry、初始化、組裝、Pipeline、模組與 Adapter、評估純邏輯 | 應可獨立於 UI、HTTP、Builder DB 實作及執行 |
| [05 資料與 Config](05_data_contracts_search_design.md) | ParsedDocument／Chunk、Schema、Config、欄位、版本與變更規則 | 精確拼字、預設值、nullable、SDK 等尚未全部凍結；完整 YAML 目前是討論草案 |
| [06 UI 開發](06_ui_development_spec.md) | 畫面／互動、基本／進階設定、CSV、AI 助手、預覽、測試與修改 | 保留已確認的按鈕、提示與收合行為；Mock 不代表後端能力完成 |
| [07 Backend／Runtime 串接](07_backend_runtime_integration.md) | API、管理資料、任務、生命週期、持久化、服務整合及獨立部署 | 呼叫 04 的相同 Engine；API／儲存細節仍有待決事項 |
| [08 開發計畫與決策](08_implementation_plan.md) | M0～M6、驗收、D／Q-ID、歷史要求對照與未決政策 | 這是決策狀態的主責文件，依階段處理阻擋，無須先解完全部 Q-ID |

接續時先讀本交接、03（尤其 §3）、08，再依當前主題讀 05／04／07／06。本文只彙整重點，實際編輯前仍需讀取受影響章節。

## 4. 最近已釐清的核心概念

下表是已記錄決策的摘要；正式定義請以 [03 §3](../03_architecture_proposal.md#terminology) 為準。

| 重點 | 接續時應保留的方向 |
|---|---|
| Engine／Runtime／System | Engine 負責依 Config 組裝與執行模組；Runtime 加 API 服務；System 是具體 RAG 應用，直接使用 Engine 也可建立 |
| 管理階層 | Workspace → System；不增加 Group 層 |
| Config | Module 的 Method／參數與邏輯設定，包含 Schema、欄位、Prompt、模型語意 Profile、Pipeline 與邏輯服務引用 |
| 部署設定 | 環境服務 URL、Secret 引用、DB／實體索引目標、Runtime／K8s 資源等；同一 System 的同一 Config Revision 跨環境保持相同邏輯設定 |
| Blueprint | 助理先前引入的詞，使用者未指定；不設為正式領域物件，舊原型型別／匯出檔名另做 migration |
| 版本概念 | 開發規格版本、Config Revision、來源文件內容版本 source_revision、索引資料版本 index_generation 分開；具體 ID／快照／發布政策未決 |

使用者曾問「文件內容版本跟索引資料版本有不同？」：概念已補入 03 §3.4，變更範例見 [05 §2](05_data_contracts_search_design.md#identity-versions)。這裡的來源文件不是 03～08 Markdown 規格；也不能因名詞已說明，就宣稱快照或原子發布方案已核可。

## 5. 接續時容易遺漏的既有要求

| 主題 | 必須保留的需求／基線 | 主責文件 |
|---|---|---|
| 技術背景 | 使用者明確說明部門使用 LangChain／LangGraph；Haystack 是早期比較候選，未被選定；精確版本及 Web／前端框架仍待 Q-001 | 03／04／08 |
| Pipeline | 固定 Ingestion／Inference 骨架，透過 Config 選擇方法及受控組合；通用 DAG 編輯器列為後續 | 03／04 |
| 資料形狀 | ParsedDocument 五個頂層 key；Chunk 六個，vectors 放在 Chunk；下游不強制回查 ParsedDocument | 04／05 |
| CSV／Schema | CSV 每列映射為一份標準 record；先設定或從 CSV＋AI 開始均可；Import 映射一次，Parsing 不重映射 JSON | 04／05／06 |
| 欄位用途 | 可分別選擇切分、Embedding、儲存、全文、向量、Filter、Rerank、Generation 用的欄位；具名 vectors 對應來源 fields | 04／05 |
| Local Search | FAISS＋BM25＋Chunk Store；MongoDB 用於保存 Chunk／vectors 及重啟重建，不在此架構中做向量搜尋；初期同程序／單副本 | 03／04／07 |
| Fusion | 目標需可配置策略及「在哪一步合併」；逐 Query Score Sum→跨 Query RRF 是已提出情境；具體支援路徑、stages、預設尚待 Q-014 | 04／05／06／08 |
| 原型融合基線 | 現有 Prototype 為所有 Query×欄位單層融合、Rerank 前執行；Sum Score 不自動正規化，RRF k=60 是既有基線，不能取代目標需求 | 04／08 |
| LLM／Prompt | System 共用 LLM 清單、以 llm_ref 引用；Query Prompt 可編輯；Generation 兩層模板並有範例／套用；Rerank 依平台契約，不能宣稱所有服務格式通用 | 04／05／06 |
| UI／API 說明 | Parsing 初始只顯示結構化 JSON，其餘格式／設定預設收合；未 Ingestion 也能查看 Ingest／Inference API 說明 | 06／07 |
| Filter／collection | Indexing 選可過濾欄位，Retrieval／本次 Query 設條件；eq／in、條件與 ACL 取 AND、Top-K 前限制；collection 由 Workspace＋System 自動命名 | 04／05／06／07 |
| 修改 Config | 有效 Ingestion 設定改動需重新 Ingestion；只改 Inference 設定需重測；未啟用草稿不影響有效設定 | 05／06／07 |
| 交付 | Export 給 FTEST／ENT，使用單位自行 K8s 部署；獨立 Runtime 不依賴 Builder；不隨匯出搬資料或自動建立外部模型／DB | 03／07 |
| 圖面 | 保留 03 §4 的 L1／Infra 版面、框、標籤與連線要求；L1 的 SVG 維護固定版面，若另改圖須同步 Mermaid／SVG／PNG | 03／diagrams |

完整已確認方向與既有基線見 [08 §3](08_implementation_plan.md)；歷史要求對照見同文件 §10，不只依本摘要實作。

## 6. 尚未完成與後續討論

目前是**可供開發討論的規格草案**。公開 Contract、部分預設值、服務整合及生命週期仍未凍結；Engine／Runtime／Builder Backend 也尚未實作。原型測試和文件檢查通過，不能代表真實模型／資料庫／K8s 已驗證。

08 保留 27 項帶有 OPEN 細節的 Q-ID。建議沿用其 §7 優先順序，先處理下表前幾組，再依使用者指定的主題展開：

| 討論群組 | 追蹤位置 | 待補的內容 |
|---|---|---|
| 技術與正式契約 | [Q-001](08_implementation_plan.md#q-001)、[Q-002](08_implementation_plan.md#q-002) | 版本、框架、正式 Schema／SDK／預設值、原型 migration |
| 可執行的模型與搜尋基線 | [Q-003](08_implementation_plan.md#q-003)、[Q-004](08_implementation_plan.md#q-004)、[Q-011](08_implementation_plan.md#q-011) | 首組服務與 Profile、Tokenizer／溢位、FAISS／BM25／分數語意 |
| 資料身分、更新與可見性 | [Q-007](08_implementation_plan.md#q-007)～[Q-010](08_implementation_plan.md#q-010)、[Q-012](08_implementation_plan.md#q-012)、[Q-015](08_implementation_plan.md#q-015) | ID／revision、重送／刪除、partial／原子性、Query 併發、MongoDB 恢復、有效配置與索引綁定 |
| 格式、權限與 Filter | [Q-005](08_implementation_plan.md#q-005)、[Q-006](08_implementation_plan.md#q-006)、[Q-013](08_implementation_plan.md#q-013) | 首批 Parser／OCR、metadata／ACL、缺值及多值過濾語意 |
| 融合計畫 | [Q-014](08_implementation_plan.md#q-014) | 前／後 Rerank、單層／兩層、分組、K／N、預設及 Config 形狀 |
| Backend／Runtime | [Q-016](08_implementation_plan.md#q-016)、[Q-017](08_implementation_plan.md#q-017)、[Q-019](08_implementation_plan.md#q-019)、[Q-020](08_implementation_plan.md#q-020) | 管理儲存、Timeout／重試／取消、API／認證、DEV 多 System 隔離 |
| UI、AI、評估與交付 | [Q-018](08_implementation_plan.md#q-018)、[Q-021](08_implementation_plan.md#q-021)～[Q-027](08_implementation_plan.md#q-027) | 指標／Gate、部署 Bundle、自訂 Python、fallback、真實助手、剩餘 UI 分組、測資、效能／成本與觀測目標 |

上表以範圍縮寫部分 Q-ID；完整候選、負責角色與阻擋階段只維護於 08。尤其 Fusion 時點配置、Parsing 收合等上位需求已有方向，OPEN 是剩餘細節，不能把需求本身重新降級。

## 7. 歷史對話核對的範圍

- 前一輪以主題檢索可取得的歷史片段，並與 repository 規格、原型及圖面比對；08 §10 記錄 U／B／P／O 證據分級與涵蓋對照。
- **尚未完成依確切標題「技術選型」（2026-10-12 15:04）取得並逐則核對整串全文。**後續依標題搜尋也未能確認完整來源，因此不能宣稱該串所有決策已整合完畢。
- 「Elasticsearch RRF 檢索」是同專案另一串討論，包含融合策略及合併時點需求；其要求已記錄，但不能視為「技術選型」整串內容。
- 若回到原串看到未納入的明確使用者決策，請列出來源、時間、對應 D／Q-ID 及受影響章節；有衝突時釐清適用範圍與先後，不憑助理先前摘要或文件日期自行定案。

## 8. 下一個對話的工作方式

1. 先確認分支最新提交與工作樹狀態，再讀交接、03、08；不要把本文件的基準提交固定成永久最新版。
2. 承接使用者當下指定的文件主題，補齊該主題的規則、範例、例外與驗收。需要新決策時，提出具體選項並記錄 Q-ID。
3. 使用者確認後，同步主責規格、08 的決策／問題狀態，以及受影響的範例／引用；未決之處保留狀態，不默默替使用者定案。
4. 保留 D／Q-ID 的可追蹤性；發現先前誤記則說明修正依據，避免把建議改寫成使用者原話。
5. 文件變更檢查連結／錨點、JSON／YAML 範例與跨文件一致性；涉及程式時再執行對應測試並記錄真實驗證範圍。
6. 沿用現有工作分支與 PR。使用者先前已要求更新 GitHub，並明確要求推送前確認是否需要 pull；先 fetch／比較遠端、保留既有修改，必要時整合遠端後再提交推送。不得強制覆寫遠端或自行合併主分支。

本次交接沿用 03～08 v0.12 的規格語意，新增接續入口，未新增產品技術決策。

## 9. 可貼到另一個對話的接續說明

```text
請接續同專案「技術選型」的開發文件撰寫。
GitHub：SunnyWenwen/rag_platform，分支 docs/rag-system-factory。
請先讀取最新版交接文件：
https://github.com/SunnyWenwen/rag_platform/blob/docs/rag-system-factory/docs/documentation_handoff.md
再讀 03 的名詞／架構與 08 的決策／待決清單，保留已確認方向，依我接下來指定的主題繼續補文件。
前一輪並未完整核對「技術選型」整串歷史；若本串另有未納入的決策，請具體比對並補正。
文件更新後同步相關規格及 08，推送前先確認遠端是否需要整合。
```
