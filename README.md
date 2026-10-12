# RAG Platform

Config-driven RAG System Factory 設計討論專案。

本專案規劃透過 UI 設定模組化 RAG、執行 Ingestion / Inference 測試、QA Evaluation，以及匯出 Kubernetes 部署設定。

目前為架構提案與模擬原型，尚未實作可部署的 RAG Engine。

## 設計文件

- [模組目的、方法與 I/O Contract（v0.1 草案）](docs/04_module_methods_io_contracts.md)：十個模組的輸入輸出、共用資料結構、相依卡控、自訂 Python 與 LangChain／LangGraph 分工；區分 MVP 與後續候選方法。

- [UI Prototype](01_ui_prototype.html)：下載後以瀏覽器開啟，操作與指標均為模擬。
- [Architecture Proposal](03_architecture_proposal.md)：模組介面、Config、API、生命週期與 MVP 規劃。
- [L1 使用流程圖](diagrams/01_user_system_l1.png) · [Mermaid 原始檔](diagrams/01_user_system_l1.mmd)
- [Infra 架構圖](diagrams/02_infra_architecture.png) · [Mermaid 原始檔](diagrams/02_infra_architecture.mmd)

架構提案與圖保留初版設計；UI 已依下述流程簡化。提案提及的 deployment_example/ 獨立範例檔尚未納入；UI 可匯出示意 YAML，不代表可直接部署。

## UI Prototype 更新

- 單一主畫面：左側 Workspace Groups，中間 RAG System 卡片，右上角 Create RAG System。
- Create RAG System 彈窗保留原有 Ingestion / Inference 模組選項與設定。
- 各卡片以彈窗提供 Ingest、Inference、Evaluation；保留原先要求的示意 K8s YAML 匯出。
- 移除 Draft Revision、手動 Start Sandbox、Approval 與獨立 Deployment 頁面。
- Group 與 System 狀態各自隔離；重新整理會重設。所有執行與評估數據仍為模擬。
- 基本相依檢查：Chunk Overlap、數值範圍、Dense-only adapter 與 Retrieval、啟用 Rerank 時的 Top-N / Top-K。Qdrant 產品本身支援 Hybrid，此處限制只代表範例 adapter 的設定。

驗證：JavaScript 語法檢查與 DOM 互動檢查通過（建立、切換 Group、相容性、Ingestion gate、Inference、Evaluation、狀態隔離、YAML 內容）。未完成瀏覽器視覺檢查；環境無可用 Chromium，下載未成功。

## 相依卡控示範

在 Create RAG System 彈窗展開「卡控示範」，可一鍵套用四組設定（會重設彈窗內的模組設定，保留名稱）：

1. **Index 限制 Retrieval**：Qdrant Vector 範例 adapter 僅提供 Dense；Hybrid / BM25 仍顯示但停用，原 Hybrid 選擇保留並阻止建立。改選 Dense 後可建立。此為 adapter 配置限制，不代表 Qdrant 產品不支援 Hybrid。
2. **Query Embedding 繼承**：Retrieval 顯示唯讀 Model / Dimension；修改 Embedding 後同步顯示。匯出時由同一來源推導，BM25 不使用 Query Embedding。
3. **關閉 Rerank**：None 時 Top-N 保留顯示但停用；重新啟用恢復可編輯，匯出不包含未啟用的 Top-N。
4. **Top-K 限制 Top-N**：Top-K=2、Top-N=3 會標示不相容；Top-N 輸入上限為 2，手動輸入超限亦阻止建立。

另有條件欄位：Dense Weight 只在 Hybrid Search 可編輯，其他模式顯示但停用。以上 UI 規則僅為示範，正式 Engine 仍需後端再次驗證。

驗證：四組 DOM 互動檢查及既有基本流程檢查通過；包含停用選項可見、失效值保留、繼承更新、選項恢復、數值上限與匯出設定。尚未完成瀏覽器視覺檢查。
