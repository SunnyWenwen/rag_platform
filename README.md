# RAG Platform

Config-driven RAG System Factory 設計討論專案。

本專案規劃透過 UI 設定模組化 RAG、執行 Ingestion / Inference 測試、QA Evaluation，以及匯出 Kubernetes 部署設定。

目前為架構提案與模擬原型，尚未實作可部署的 RAG Engine。

## 設計文件

- [UI Prototype](01_ui_prototype.html)：下載後以瀏覽器開啟，操作與指標均為模擬。
- [Architecture Proposal](03_architecture_proposal.md)：模組介面、Config、API、生命週期與 MVP 規劃。
- [L1 使用流程圖](diagrams/01_user_system_l1.png) · [Mermaid 原始檔](diagrams/01_user_system_l1.mmd)
- [Infra 架構圖](diagrams/02_infra_architecture.png) · [Mermaid 原始檔](diagrams/02_infra_architecture.mmd)

本次匯入既有六份文件，保留原始內容。提案提及的 deployment_example/ 獨立範例檔尚未納入；UI 可匯出示意 YAML，不代表可直接部署。
