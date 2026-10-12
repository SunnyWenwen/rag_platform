# Config-Driven RAG System Factory — Architecture Proposal (Discussion Draft)

> Version 0.1 · 2026-10-12 · Audience: Engineering / Platform / Management
>
> 此文件描述目標架構與提議的介面；原型與 K8s YAML 均為 **示意**，不是已實作的正式產品。

## 1. Executive Summary

**目標**：提供企業內部「設定 → 自動組裝 RAG Engine → Sandbox 實測 → QA Evaluation → Release → K8s Deployment」自助式平台。使用者無須為每個 Use Case 自行開發 RAG pipeline 或 Docker image。

**產品定位**：不是單純的文件聊天工具，而是能產出可版本化、可測試、可重現、可部署 RAG Runtime 的 **RAG System Factory**。

**非目標（初期）**：不建立通用 DAG 視覺化程式語言；不要求所有 RAG 模組可由任意第三方拖拉組合；不保證點選 Save 後文件即刻完成索引；不將使用者的測試數據直接複製至正式環境。

## 2. Product Information Architecture (UI Prototype)

| 畫面 | User 操作 | Platform 回應 |
|---|---|---|
| Projects | Create / Clone / Open RAG Project | Project ID、ACL、配置歷史 |
| Pipeline Builder | 設定 Ingestion + Inference 各模組及參數 | Schema / Compatibility Validation；儲存 Config Revision |
| Sandbox Runtime | Start / Stop Sandbox | Resolve Components、Bind Resources、Status / Health / Endpoint |
| Ingestion Studio | Upload / Import / Sync Data；查看 Job | 非同步 Job、解析/切片/索引進度、錯誤重試 |
| Inference Playground | Query、top_k override、Inspect Traces | Answer、Citations、Retrieved Chunks、Latency、Model Token Usage |
| Evaluation | Upload QA Set / Run / Compare | Dataset Version、Retrieval & Answer Metrics、Regression Gate |
| Release & Deployment | Approve Version / Export Bundle | Immutable Config、Image Digest、Helm / K8s、External Secret References |

Prototype 實作在 `01_ui_prototype.html`：**互動只在瀏覽器內模擬**，不會實際呼叫 Embedding / LLM / K8s。

## 3. Functional Design

### 3.1 Modular RAG Engine

| Pipeline | Module | 最低可行 Implementation | 可調參數 | Compatibility Notes |
|---|---|---|---|---|
| Ingestion | Data Import | File Upload / Object Storage | Connector、Path、Incremental Sync | Source ACL、格式及檔案大小限制 |
| Ingestion | Parsing | PDF/Text parser | OCR on/off、Layout Strategy | OCR 需額外資源 |
| Ingestion | Chunking | Recursive / Header-aware | size、overlap、metadata | 改動後通常需重新索引 |
| Ingestion | Embedding | Enterprise Model Gateway | model、dimension、batch | Query/Doc Embedding 必須匹配；Index Dimension 必須相符 |
| Ingestion | Indexing | Existing Elasticsearch/OpenSearch | index schema、alias、metadata | Hybrid 需要稀疏全文與向量欄位；Alias 切換應原子化 |
| Inference | Query Transform | None / Rewriter | template、queries count | 可能增加成本/延遲 |
| Inference | Retrieval | Dense / BM25 / Hybrid | top_k、filters、fusion | 要與 Index Backend 能力相容 |
| Inference | Rerank | None / Cross Encoder | top_n、model | Candidate size >= top_n |
| Inference | Generation | Enterprise LLM Gateway | model、temperature、prompt | Prompt/version/guardrails 要可追溯 |
| Evaluation | Evaluation | Batch Evaluator | dataset、metrics、threshold | 長任務走非同步 Job |

**Plugin Contract 建議**：`name`, `version`, `input_schema`, `output_schema`, `config_schema`, `validate()`, `initialize()`, `run()`，必要時提供 `health()`/`capabilities()`；Driver 對外服務內部封裝。建議採用 schema-first validation，並確保向量維度、Embedding/Index 組合、Rerank top_n、Metadata Filter、Multi-tenant ACL 相容。

### 3.2 Config 範本（概念示意）

```yaml
apiVersion: rag.company/v1
kind: RAGBlueprint
metadata:
  project: customer-support-rag
  revision: draft-7
spec:
  engineVersion: 1.0.0
  ingestion:
    import: {type: object-storage, path: s3://example/docs}
    parsing: {type: pypdf, ocr: auto}
    chunking: {type: recursive, size: 512, overlap: 64}
    embedding: {type: enterprise-api, model: bge-m3, dimension: 1024}
    indexing: {type: elasticsearch, index_alias: cs-rag}
  inference:
    query_transform: {type: none}
    retrieval: {type: hybrid, top_k: 10}
    rerank: {type: cross-encoder, top_n: 5}
    generation: {type: gateway, model: company-llm, temperature: 0.2}
  evaluation:
    dataset_ref: datasets/cs-golden-v3
    gates: {recall_at_5_min: 0.8, faithfulness_min: 0.85}
```

**注意**：這是建議 schema，不是 Haystack 或任一家雲端的既有格式。現場真正實作的 Component 名稱須以 Module Registry 能力為準。

### 3.3 Engine 啟動策略（重要 ADR）

**Option A — Shared Sandbox Engine（推薦 MVP）**

- Control Plane 管理多個 Project 的 Configuration；Sandbox 裡有共享 Pipeline Executor / Worker Pool。
- 用 `project_id + config_revision + run_id` 載入設定並組裝 Pipeline；Ingestion 透過 queue / job 非同步處理。
- 優點：Config 提交後快速可測，不需每個 Use Case 重新建 Pod；資源利用率高。
- 代價：需要 Tenant Isolation、ResourceQuota、Access Control、Concurrency Control。

**Option B — Dedicated Sandbox Runtime（高隔離場景）**

- 每個 Project / Revision 建自己的 inference Deployment，並針對 ingestion / eval 建立 Jobs。
- 優點：效能與安全隔離清楚，易於貼近 Prod。
- 代價：Provisioning/模型暖機成本較高，不能承諾「馬上起來」。

**建議**：MVP 使用共享 Sandbox + Project-scoped Config/Index；正式 Release 產生 Dedicated Runtime。敏感部門可提供 Dedicated Sandbox 為進階選項。啟動 Ready、Index Ready 是不同狀態。

### 3.4 建議生命週期與狀態

```text
Draft -> Validated -> Provisioning -> Sandbox Ready
                                         |
                                         v
                            Ingestion Pending/Running/Failed/Completed
                                         |
                                         v
                             Tested -> Evaluated -> Approved
                                         |
                                         v
                         Immutable Release -> Exported -> Deployed
```

修改 Index-time Config（Parsing / Chunking / Embedding / Index Schema）需標記索引失效、安排 Re-index；修改 Query-time 參數（top_k / filters）通常可直接重跑 inference/evaluation。任何改動若要 Release，都應重新驗證對應 Config Revision 的 Evaluation Results。需明確定義「Release 與 Index Snapshot 是否綁定」、「Prod 是否重新 ingestion」。

## 4. Control Plane vs Data Plane

**Control Plane**：UI、API Gateway、Auth/RBAC、Project/Config Store、Module Registry、Compatibility Validator、Runtime Controller、Job Manager、Release Builder、Audit/Approval。其重點是資源生命週期、審核與追溯，而不是實際跑模型。

**Data Plane**：Ingestion Jobs/Workers、Inference API、Evaluation Jobs；連接 Object Storage、Index Backend、Model Gateway，產生 Logs/Metrics/Traces。根據組織規範共享或隔離。

**K8s Workload 角色**：

- Inference：Deployment + Service (+ HPA)，需 Ready Probe、資源 Request/Limit、Graceful Shutdown。
- Ingestion：Job / Queue Worker（可再加排程 CronJob），支援 idempotency、retry、checkpoint、dead-letter。
- Evaluation：Job，結果記入 Evaluation Store / Object Storage，不在長期 inference Deployment 中同步執行。
- Config：ConfigMap 或掛載檔案；**敏感憑證不進 Config / Export Bundle**，使用外部 Secret / Secret Manager / Service Account。

## 5. Release Bundle / GitOps 建議

Production-ready export 結構建議：

```text
release-2026-10-12-001/
  release-manifest.json      # config hash / image digest / module versions
  blueprint.yaml             # 已凍結且通過 schema validation
  helm/
    Chart.yaml
    values.yaml              # environment overrides
    templates/
      deployment.yaml
      service.yaml
      configmap.yaml
      hpa.yaml               # optional
      job-ingestion.yaml     # on-demand execution pattern
  reports/
    evaluation-summary.json
    compatibility-report.json
```

**正式環境應由 CI/GitOps 部署**，不是平台在 UI 中直接對 Prod Cluster `kubectl apply`。建議把 Chart/Values 發布至內部 Git Repo，CI 執行 `helm lint/template`、K8s schema 驗證、image/security scan，再透過 Argo CD 或內部 CD 工具套用。Export 需鎖定 `engine_image_digest`、Module Version、Model ID、Config Hash、Eval Dataset/Run ID；不會包含 index 資料或機密。正式環境的 Index、Object Storage、Network / RBAC 應使用環境專屬連線與配置。

`deployment_example/` 僅提供示範 Manifest，不含真正 Engine Image，**不可視為可部署產物**。

## 6. API Surface（建議）

| Method | Path | 用途 |
|---|---|---|
| POST | `/api/projects` | Create Project |
| POST | `/api/projects/{id}/blueprints:validate` | Schema/Compatibility Validation |
| POST | `/api/projects/{id}/revisions` | Save immutable Config Revision |
| POST | `/api/projects/{id}/sandboxes` | Provision / Start Sandbox |
| GET | `/api/sandboxes/{id}` | Runtime Status / Endpoint |
| POST | `/api/projects/{id}/ingestion-jobs` | 建立非同步 Import/Index Job |
| GET | `/api/ingestion-jobs/{id}` | Job Progress / Errors |
| POST | `/api/projects/{id}/queries` | Debug Inference + Trace |
| POST | `/api/projects/{id}/evaluation-runs` | 啟動 Batch Evaluation |
| GET | `/api/evaluation-runs/{id}` | Metrics / Run Comparison |
| POST | `/api/projects/{id}/releases` | Approve / Freeze Release |
| POST | `/api/releases/{id}/exports` | 產生 Helm / K8s Export Bundle |

上述 Endpoint 是 **API Proposal**，並非現成服務的既有 API。

## 7. Evaluation 設計

建議 QA Dataset 最少有 `question`, `expected_answer`；若要計算 Ground-truth Retrieval Metrics，增加 `reference_doc_ids` 或 `relevant_chunk_ids`。對 LLM 評估，須明確區分：

- **Retrieval**：Recall@K、MRR、nDCG（需要標註 Relevant Documents/Chunks）。
- **Answer**：Answer Correctness、Faithfulness / Groundedness、Citation Precision（通常需要 Ground Truth 或 Judge）。
- **Operations**：P50/P95 latency、Tokens/Query、Cost、Failure Rate。
- **Regression Gate**：與 Baseline 的分數差、門檻、失敗案例、人工核准政策。

每個 Evaluation Run 必須綁定 `dataset_version + config_revision + index_snapshot + judge_model_version`，否則重跑結果無法可靠比較。若沒有 Ground Truth，不能聲稱計算了正確的 Recall@K。

## 8. 開發優先序與里程碑

| Phase | 範圍 | 可驗收成果 |
|---|---|---|
| P0 — Foundation | 固定 Pipeline + Schema-driven Config + Config Validation + Project/Revision | 透過 JSON Config 組裝單個可執行 Engine |
| P1 — Self-service | UI Pipeline Builder、Sandbox 管理、Ingestion Job、Inference Playground | 使用者不寫程式即可跑完整端到端 RAG |
| P2 — Quality | QA Upload、Evaluation Runner、Traces、Baseline Comparison | 同版本具備可追溯的品質報告與 Regression Gate |
| P3 — Delivery | Immutable Release、Helm Export、CI Validation、GitOps | 可在內部 K8s 複製部署已核准 Runtime |
| P4 — Advanced | 多模態、Graph Retrieval、Plugin Marketplace、Fine-grained Tenant Isolation | 擴充特殊領域與複雜 RAG |

**建議 MVP 先限制組合爆炸**：每個 Module 1–2 種 Implementation、先支援 1 個 Index Backend 與 1 個 Model Gateway，並把 Schema/Compatibility Validation 做好；等測試迴圈穩定再引入更多 Module。

## 9. 管理層決策點

1. 平台主要是 **RAG-as-a-Service**（統一 shared inference API）還是 **System Factory**（各部門獨立匯出部署）？兩者可以共存，但 Security/Cost Model 不同。
2. Sandbox / Prod 是否共用 Elasticsearch、Object Storage、LLM Gateway？需要使用專屬 Index/Namespace 或獨立 Cluster 嗎？
3. First-class backend：現有 Elasticsearch / OpenSearch，或引入新 Vector DB？
4. Evaluation Gate 是建議性報告還是 Prod Release 的強制條件？誰有 Approve 權限？
5. 部署策略為下載 YAML 手動交付，還是標準化 Helm + GitOps？
6. 每個 Project 期望的 Concurrent User、索引資料量、GPU 需求、SLO、平均 Provisioning Time？
7. 是否需要 Knowledge Graph / Legacy Knowledge Extraction 作為另外一種 Ingestion Plugin，而非綁死在標準文件 RAG？

## 10. Open-source 參考（不是替代整套平台）

- **Haystack**：Component/Pipeline、Typed I/O、Pipeline serialization 設計可作 Engine 的參考，也可用於實作，不必從零造輪子：<https://docs.haystack.deepset.ai/docs/creating-pipelines>。
- **Langfuse**：Trace、Evaluation / Dataset / Experiment、Self-hosted Kubernetes 可作 Observability/Evaluation 的參考：<https://langfuse.com/self-hosting/deployment/kubernetes-helm>。
- **Argo CD + Helm**：GitOps 應用交付與版本對齊：<https://argo-cd.readthedocs.io/en/stable/user-guide/helm/>。

**實作準則**：能套用既有成熟產品的層面就優先整合，平台自行開發的核心應集中在 Config/Module Contract、Lifecycle Orchestration、Cross-module Compatibility、Release Reproducibility。