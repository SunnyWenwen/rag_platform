# RAG Builder

Config-driven RAG System 建立與測試平台。

本專案規劃透過 UI 設定模組化 RAG、執行 Ingestion / Inference 測試、QA Evaluation，以及匯出 Kubernetes 部署設定。

目前為架構提案與模擬原型，尚未實作可部署的 RAG Engine。

**名詞**：RAG Builder 是開發平台；RAG System 是使用者建立的個別系統；RAG Runtime 是可獨立部署的 API 執行服務；RAG Engine 是其 Pipeline 核心。

## 設計文件

- [資料契約與索引設計討論結論（v0.7）](docs/05_data_contracts_search_design.md)：最新 ParsedDocument／Chunk、欄位映射、Embedding、ES／Local Search、MongoDB 持久化、Hybrid 與 UI 卡控；區分已確認方向與待定建議。

- [模組目的、方法與 I/O Contract（v0.2 草案；資料契約見 v0.7）](docs/04_module_methods_io_contracts.md)：十個模組的輸入輸出、共用資料結構、相依卡控、自訂 Python 與 LangChain／LangGraph 分工；區分 MVP 與後續候選方法。

- [UI Prototype](01_ui_prototype.html)：下載後以瀏覽器開啟，操作與指標均為模擬。
- [Architecture Proposal v0.7](03_architecture_proposal.md)：RAG Builder／獨立 Runtime 分工、共用 Engine／API、外部服務環境設定、模組契約與 MVP 規劃。
- [L1 使用流程圖](diagrams/01_user_system_l1.png) · [Mermaid 原始檔](diagrams/01_user_system_l1.mmd)
- [Infra 架構圖](diagrams/02_infra_architecture.png) · [Mermaid 原始檔](diagrams/02_infra_architecture.mmd)

架構提案與 Infra 圖已整合 2026-10-14 的最新討論：RAG Builder Control Plane 明確分為 Frontend／Backend，接入 tSSO；DEV RAG Runtime 負責測試執行。Backend 的建立／設定連線指向整個 DEV RAG Runtime，由 Runtime 依 Config 組裝 Pipeline 執行實例，並匯出 FTEST／ENT YAML（文件形狀節點），使用單位自行於 K8s 進行 CD 部署；Secret Vault、部署依賴與觀測工具位於獨立 Runtime 框外。UI 可匯出示意 YAML，不代表可直接部署；Engine、Runtime API 及完整部署 Bundle 尚未實作。

## UI Prototype v0.7（2026-10-14）

- Create／Edit 最前段增加 Document Schema；預設只提供必填 fields.text。可新增 fields／metadata，設定 string／number／boolean／array、必填、JSON 預設值及 input／parser 來源；未宣告欄位預設拒絕。
- Ingest 本版先支援 ≤1 MB CSV／JSON。CSV 每列是一筆文件，映射目標包含 document_id／source_revision／fields.*／metadata.*；預覽 API payload 與 ParsedDocument，型別／必填／重複 ID 錯誤會阻止模擬匯入。成功後保存 CSV 映射；JSON 直接使用標準 records 契約。
- 提供「先設定 Config」與「從 CSV 開始 · AI 設定助手」兩種入口；確認助手的 Schema、映射與 Pipeline 草稿後，CSV 可帶到 Ingest 再執行。
- 保留 Workspace Groups／System 卡片；新增 Edit Config，沿用 Create 介面及獨立草稿。
- Chunking 只留 Recursive／Header-aware，Size／Overlap 使用 Tokens，支援 Tokenizer、分隔符及標題層級設定。
- Embedding 僅 DEV test use／Embedding API；依服務來源展開 URL、認證引用、模型、維度與 Tokenizer 等設定。
- ES 提供 DEV／自行連線；Local Search 只有選 MongoDB 時顯示 DB 設定。
- Index collection 自動由 Workspace＋名稱＋System ID 產生，改名不影響既有實體名稱。
- LLM 服務設定集中管理此 RAG System 的服務清單；Query Transformation／Generation 以 llm_ref 下拉引用，部署時相同服務只需填一次。
- Query Transformation 支援 None／Rewrite／Multi-query；Rewrite／Multi-query 各自可編輯 Prompt，提供 query／count 變數驗證與預覽；原始問題可加入搜尋。
- Retrieval 移除 Implementation，依選取的全文／向量欄位推導模式；多 Query 或多欄位使用 RRF。
- Rerank 提供 None／DEV／Rerank API、內容欄位與可查看的固定 Request／Response 範例。
- Generation 從共用 LLM 清單選擇服務，提供兩層模板、插入變數、完整 Prompt 預覽，以及「模板說明與範例／套用範例」。
- Ingestion API records 使用 document_id／source_revision／fields／metadata，並預覽 Parsing 後的 ParsedDocument；fields／metadata 已使用 Schema 的目標名稱，Parsing 不再重複映射；結構資訊由 Parser 產生。
- Indexing 選可過濾的完整欄位路徑；Retrieval 設定 eq／in 的預設詞值，Inference 可輸入本次 filters，全部以 AND 組合。上游欄位失效會阻止儲存；新增過濾索引需 Ingestion，改詞值只需重測。
- Ingestion／Inference 的「查看 API 端點」提供 Base URL、認證、JSON／multipart、cURL、回應及錯誤範例；Ingestion 另有 run_id 進度查詢。端點與搜尋／過濾仍未實作。
- AI 設定助手明示為規則模擬：可讀小型 JSON／CSV／TXT／MD 樣本（含 records[].fields），先呈現設定差異再套用；不呼叫 AI、不自動 Ingestion。
- 檢查訊息統一標示 [模組名稱]；刪除正在使用的 LLM 會保留失效引用並阻止儲存。
- 編輯 Ingestion 配置後標記需重新匯入；僅 Inference 變更不用重建，但清除舊示意評估。
- 匯出先檢查 DEV 資源，分為待設定草稿及已填妥設定；不匯出真實憑證，Local Search 固定單副本。

所有模型／DB 操作仍是 UI 模擬；Check Settings 只檢查格式。重新整理會重設資料。YAML 使用示例 Engine Image，沒有部署服務或搬移索引。

## 操作示例

1. Create → Document Schema：定義 fields／metadata；接著到 Chunking：改 Header-aware，查看 Tokens 與進階分隔符。
2. Embedding／Indexing：切換 DEV 與自行提供，觀察必填連線設定。
3. Generation → 模板說明與範例：查看兩筆 Chunk 如何組成 context，套用範例。
4. AI 設定助手：輸入「改用 Local Search」，查看差異後套用；樣本可用 JSON `[{"content":"原文","abstract":"摘要","title":"標題"}]`。
5. 建立 → Ingest：上傳 CSV，將 content 映射到 fields.text、department 映射到 metadata.department；檢查預覽後模擬匯入 → Edit Config：改 Chunk Size 後會要求重匯；改 Generation Temperature 則不需重匯。
6. Retrieval → 新增過濾條件：選 metadata.department、eq、manufacturing；再到 Inference 的本次查詢過濾輸入 JSON 條件，與預設條件 AND。
7. Export YAML：DEV 設定可下載草稿；補齊自己的服務 URL 後可匯出格式已填妥的示意設定。
8. System 卡片 → Ingest／Inference → 查看 API 端點：查看 Runtime API、請求與回應；尚未完成 Ingestion 也能查看 Inference 說明。

## 驗證

執行 `node tests/prototype.test.cjs`，使用無依賴 VM／DOM stub 檢查 52 項設定與狀態規則（包含 3 項非同步樣本讀取）。另以 jsdom 驗證實際表單事件、條件欄位、建立／編輯、AI 套用、Prompt、匯出及 API 說明。已通過 Chromium 互動檢查及 1440px／390px 桌面與手機版面檢查；無頁面 JavaScript 錯誤。檢查涵蓋 Create、API／DB 條件欄位、Prompt 範例、AI 套用、Ingestion、Edit 影響與 Export gate。


共用 LLM／Prompt 另經 Chromium 實測：新增、改名、選擇、刪除、API 設定、Prompt 即時驗證與預覽、共用匯出資源及手機寬度。

API 說明另經 Chromium 實測：兩個操作視窗的開啟／返回、尚未 Ingestion 時查看 Inference 說明、JSON／cURL 範例與手機寬度；沒有送出 HTTP 請求。





Filter／fields 另經 Chromium 驗證：完整欄位路徑、eq／in 值輸入與失效卡控、ParsedDocument 範例、查詢附加條件、手機寬度與匯出。全部為本機模擬，不執行真實資料搜尋。





Document Schema／CSV 流程另經 jsdom 與 Chromium 驗證：兩種起始情境、metadata 必填與映射、保存映射、API／ParsedDocument 預覽、無效 JSON 卡控、Schema 編輯影響／取消，以及 1440px／390px 版面。CSV 讀取、映射、Schema 檢查在瀏覽器執行；LLM、OCR、Embedding、搜尋及 Runtime API 仍是模擬，未送出 HTTP。自動 ID 只在本次上傳內固定，更新既有文件需映射穩定 ID；source_revision 自動值目前僅為示意。
