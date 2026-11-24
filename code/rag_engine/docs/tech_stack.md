# Runtime 技術選型（定案）

更新日期 2026-11-23。適用 rag_engine 的 Engine、Components 與 Runtime API（M1～M3）。規格來源是 rag_platform 的 `docs/` 與 `schemas/`，本 repo 的 `src/rag_engine/contracts/data/` 為其複本。

## 決定一覽

| 項目 | 決定 | 鎖定版本 | 理由 |
|---|---|---|---|
| 語言 | Python 3.12（Image 為 3.12.13） | `>=3.12,<3.13` | 部門標準；LangGraph 與 ES client 皆支援 |
| 套件與鎖檔 | uv、`pyproject.toml`、`uv.lock` | uv 0.11 | 鎖檔可重現；公司 PyPI 映像用 `UV_INDEX_URL` |
| 專案結構 | 單一套件 `rag-engine`，src layout | — | 分層 `runtime → engine → components → adapters → core → contracts`，由 import-linter 強制。Python／AI 助手可直接 import Engine，不必經 HTTP |
| HTTP 服務 | FastAPI＋Uvicorn，**單一 worker** | FastAPI 0.165、Uvicorn 0.54 | 文件占用、Queue、Run 都在程序記憶體，一個 Pod 只能有一個程序 |
| 契約驗證 | `jsonschema`＋`referencing` 直接載入 rag_platform 的 Schema | jsonschema 4.26 | Builder 與 Runtime 共用同一份 Schema。Schema 大量使用 `if/then`、`oneOf`、`unevaluatedProperties`，自動轉 Pydantic 模型會失真，所以邊界以 Schema 驗證，內部用 frozen dataclass |
| 流程引擎 | LangGraph `StateGraph` | 1.2 | 每個載入的 Config Revision 編譯一次；每次請求的參數經 `config["configurable"]` 傳入。不用 checkpointer、不用 LangGraph Server |
| 索引 | Elasticsearch 8.19.8，官方 async client | elasticsearch-py 8.19 | 對齊 PLED 叢集。BM25 與 kNN 分路查詢，RRF／Sum Score 在 Python 融合，不依賴 ES 原生 RRF 的版本與授權差異 |
| 中文分析 | `stconvert`（t2s）char filter＋IK：寫入 `ik_max_word`、查詢 `ik_smart` | 外掛 8.19.8 | IK 詞典以簡體為主，先把繁體轉簡體再斷詞；`_source` 保留原文。`analysis-smartcn` 已安裝，保留作備案 |
| 向量欄位 | `dense_vector` 1024 維、`cosine`、`index_options: int8_hnsw` | — | bge-m3 dense 輸出；int8 量化省記憶體約 4 倍。設定寫在 resources，進入索引指紋 |
| Embedding | bge-m3 dense，由獨立服務提供 OpenAI-compatible `POST /v1/embeddings`（例如 TEI） | — | Runtime Image 不含 torch 與權重，模型可獨立擴充。v1 只用 dense，不用 sparse／ColBERT |
| Tokenizer | Hugging Face `tokenizers` 讀 bge-m3 `tokenizer.json`，打包進 Image | tokenizers 0.23 | 以 token 的字元 offset 切原文，Chunk 一定是原文子字串（Q-004）。執行期不連網下載 |
| 索引指紋 | RFC 8785 正規化＋SHA-256 | rfc8785 0.1.4 | 對齊 `index_fingerprint.v1` |
| 對外 HTTP | `httpx.AsyncClient` | httpx 0.28 | Remote API 與 Embedding 共用連線池 |
| MCP | 官方 `mcp` SDK 的 low-level `Server`＋`StreamableHTTPSessionManager(stateless=True, json_response=True)` | mcp 2.3 | 協定版本更新很快，交給 SDK 協商；實測與官方 client 協商為 `2025-11-25`。每個 System 的工具由路徑決定 |
| 部署設定 | `pydantic-settings`，環境變數前綴 `RAG_` | — | 預設值依 06 的「已確認的初始預設」 |
| Log 與追蹤 | 標準 logging 輸出 JSON，`contextvars` 帶 `request_id`、`system_id`、`run_id` | — | `X-Request-Id` 規則見 06；OpenTelemetry 列為後續 |
| 測試 | pytest＋pytest-asyncio；httpx `ASGITransport`／`MockTransport`；MCP 以 uvicorn＋官方 client 實測 | pytest 8 | ES 實機測試以 `-m es` 選擇執行 |
| 程式品質 | ruff（lint＋format）、mypy、import-linter | — | `make check` 一次執行 |
| Image 與部署 | `python:3.12.13-slim-bookworm` 多階段建置、非 root；DEV 用 `replicas: 1` 的 StatefulSet | — | 部門指定的 base image，鎖到 patch 版與 Debian 12 bookworm。見 `Dockerfile` 與 `deploy/k8s/` |

## 為什麼不這樣做

- **不用 gunicorn 或 uvicorn 多 worker**：會讓同一 Pod 有多個程序，Pod 內占用檢查失效。要擴充查詢量時，FTEST／ENT 另開 Inference Pod。
- **不從 Schema 產生 Pydantic 模型**：產生器處理不好 `if/then`、`oneOf`，會讓 Runtime 與 Builder 對同一份 Schema 有不同解讀。
- **不在 Runtime 內載入 bge-m3**：Image 會變成數 GB 且需要 GPU 排程，升級模型也要重建 Runtime。
- **不自己實作 MCP 協定**：官方 client 已用 `2026-07-28` 起跳並以 probe 協商版本，自行實作會一直追規格。
- **不用 LangGraph checkpointer**：工作狀態依規格只存在受理 Pod 記憶體，重啟從空開始。

## 待你在公司確認後填入

| 項目 | 目前的預設 | 要改的地方 |
|---|---|---|
| 內部 PyPI 映像 | 公開 PyPI | 環境變數 `UV_INDEX_URL`，或 `pyproject.toml` 的 `[[tool.uv.index]]` |
| uv 的來源 image | `ghcr.io/astral-sh/uv:0.11`（只在建置階段複製 uv 執行檔） | `Dockerfile` 的 `UV_IMAGE`，或改用公司映像 |
| CI 平台 | `ci/gitlab-ci.example.yml` 範例 | 依公司 CI 改寫，核心是 `make check` |
| bge-m3 版本 | `REPLACE_WITH_MODEL_COMMIT` | `resources/dev.yaml`、`deploy/k8s/dev-runtime.yaml` |
| PLED ES 位址規則 | `https://es{es_number}.pled.example:9200` | `RAG_PLED_ES_URL_TEMPLATE` |
