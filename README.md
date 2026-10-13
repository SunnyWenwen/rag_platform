# RAG Platform

Config-driven RAG System Factory 設計討論專案。

本專案規劃透過 UI 設定模組化 RAG、執行 Ingestion / Inference 測試、QA Evaluation，以及匯出 Kubernetes 部署設定。

目前為架構提案與模擬原型，尚未實作可部署的 RAG Engine。

## 設計文件

- [資料契約與索引設計討論結論（v0.3）](docs/05_data_contracts_search_design.md)：最新 ParsedDocument／Chunk、欄位映射、Embedding、ES／Local Search、MongoDB 持久化、Hybrid 與 UI 卡控；區分已確認方向與待定建議。

- [模組目的、方法與 I/O Contract（v0.2 草案；資料契約見 v0.3）](docs/04_module_methods_io_contracts.md)：十個模組的輸入輸出、共用資料結構、相依卡控、自訂 Python 與 LangChain／LangGraph 分工；區分 MVP 與後續候選方法。

- [UI Prototype](01_ui_prototype.html)：下載後以瀏覽器開啟，操作與指標均為模擬。
- [Architecture Proposal](03_architecture_proposal.md)：模組介面、Config、API、生命週期與 MVP 規劃。
- [L1 使用流程圖](diagrams/01_user_system_l1.png) · [Mermaid 原始檔](diagrams/01_user_system_l1.mmd)
- [Infra 架構圖](diagrams/02_infra_architecture.png) · [Mermaid 原始檔](diagrams/02_infra_architecture.mmd)

架構提案與圖保留初版設計；UI 已依下述流程簡化。提案提及的 deployment_example/ 獨立範例檔尚未納入；UI 可匯出示意 YAML，不代表可直接部署。

## UI Prototype 更新（欄位設定版）

- 維持單一 Workspace Groups／RAG System 卡片介面，以及 Create RAG System 彈窗。
- Import 顯示 Upload＋API 共用入口的設計；目前操作仍是檔案上傳模擬，未串接 API。
- Parsing：依格式設定策略，新增／移除來源欄位到 Content Schema 的映射。
- Chunking：選擇主要切分欄位、複製欄位與 metadata。
- Embedding：新增／移除 fields → vectors 映射；目前共用一組模型與維度。
- Indexing：ES／Local Search（FAISS＋BM25），選擇儲存、向量、全文與過濾欄位；Local Search 可選 Memory／MongoDB。
- Retrieval：選擇已索引欄位，Dense／BM25／Hybrid，第一版融合固定 RRF；Query Embedding 唯讀繼承。
- Rerank／Generation：分別選擇需要的內容欄位。
- ParsedDocument 五個 key 與 Chunk 六個 key 的即時示意預覽。
- 上游刪除／改名後保留失效選擇並阻止建立；不默默替換設定。
- 匯出示意 YAML 包含欄位設定與有效參數；Local Search 固定單一副本，Ingestion／Inference 必須共用程序。
- 所有操作仍為 UI 模擬，不解析文件、不呼叫模型或資料庫；重新整理重設操作。

## 卡控示範

1. 缺少全文索引：Hybrid 不相容，選項仍可見但停用；需補全文索引或改 Dense。
2. 多欄位 Hybrid：原文與摘要各自產生向量，全文搜尋原文。
3. Local／Memory：切換保存模式並查看重啟語意。
4. Top-K／Top-N：Top-K=2、Top-N=3 阻止建立。

驗證：JavaScript 使用 VM 與 DOM stub 執行，通過模組設定渲染、預設有效性、上游欄位／向量改名、儲存欄位相依、建立系統、Local YAML 副本數、None Rerank 有效參數、Top-K 卡控及資料預覽檢查。此為邏輯驗證，非完整 DOM 或瀏覽器測試；環境缺少 Chromium，尚未完成視覺檢查。
