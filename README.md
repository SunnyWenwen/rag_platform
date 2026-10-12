# RAG Platform

Config-driven RAG System Factory 設計討論專案。

本專案規劃透過 UI 設定模組化 RAG、執行 Ingestion / Inference 測試、QA Evaluation，以及匯出 Kubernetes 部署設定。

目前為架構提案與模擬原型，尚未實作可部署的 RAG Engine。

## 設計文件

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
