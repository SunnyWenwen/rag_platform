# rag_engine：Retrieval Runtime

RAG System Factory 的 Engine、內建 Components 與 Runtime API。Builder（外包）透過 DEV Runtime 的 HTTP API 管理 System；FTEST／ENT 以同一個 Image 載入單一 System Config 獨立部署。

- 規格：rag_platform `docs/`（03 Engine、05 System Config、06 Runtime API）；在本 repo 內為 [../../docs](../../docs/06_runtime_api_and_deployment.md)
- 技術選型：[docs/tech_stack.md](docs/tech_stack.md)
- 程式架構：[docs/architecture.md](docs/architecture.md)
- 交接狀態與後續工作：[docs/roadmap.md](docs/roadmap.md)
- 測試方式：[docs/testing.md](docs/testing.md)
- 開發 Agent 規則：[AGENTS.md](AGENTS.md)

## 快速開始

需要 Python 3.12 與 [uv](https://docs.astral.sh/uv/)。

```bash
make install
```

```bash
make check
```

```bash
make run
```

`make run` 以記憶體索引、hash 向量與測試資源在 `http://127.0.0.1:8080` 啟動 DEV Runtime，管理帳密 `mock`／`mock`，只供本機示範。另開一個終端機執行下列指令，會對它走完整個 Builder 流程：

```bash
make smoke
```

## 主要環境變數

| 變數 | 用途 | 預設 |
|---|---|---|
| `RAG_MODE` | `dev`（Builder 管理）或 `standalone`（FTEST／ENT） | `dev` |
| `RAG_ENV` | 索引名稱與 `_meta.env`；Builder 管理的 Runtime 固定 `builder` | `builder` |
| `RAG_RUNTIME_REF` | Catalog 回傳的 Runtime 識別 | `dev-runtime` |
| `RAG_MANAGEMENT_USERNAME`／`RAG_MANAGEMENT_PASSWORD` | DEV 管理 API 的 Basic 帳密 | 必填（dev） |
| `RAG_RESOURCES_FILE` | Embedding Profile、Tokenizer、文字分析設定 | 測試資源 |
| `RAG_INDEX_BACKEND` | `elasticsearch` 或 `memory`（測試用） | `memory` |
| `RAG_EMBEDDING_BACKEND` | `service`（OpenAI-compatible）或 `hash`（測試用） | `service` |
| `RAG_ES_URL`、`RAG_ES_USERNAME`、`RAG_ES_PASSWORD` | Builder 測試用 ES（`dev_test`） | — |
| `RAG_PLED_ES_URL_TEMPLATE` | 由 `es_number` 組出 PLED 叢集位址 | — |
| `RAG_CONFIG_FILE`、`RAG_PIPELINE`、`RAG_INDEX_GENERATION` | standalone 啟動的 Config、流程與索引世代 | — |

限流、Queue、保留期等其餘設定見 `src/rag_engine/runtime/settings.py`，預設值依 06 的「已確認的初始預設」。

## 目錄

```
src/rag_engine/
  contracts/   rag_platform 的 Schema、OpenAPI、Descriptor 複本（勿手改）
  core/        型別、錯誤、Filter、RFC 8785、resources
  adapters/    IndexStore（記憶體／ES）、ES mapping、Embedding、Tokenizer
  components/  切分、Embedding、結果處理、Remote API
  engine/      編譯器、指紋、LangGraph 流程、索引寫入
  runtime/     FastAPI、認證、生命週期、匯入控制、查詢、MCP
tests/         單元、HTTP 流程、MCP、ES（實機測試需 RAG_TEST_ES_URL）
deploy/k8s/    DEV Runtime StatefulSet、bge-m3 Embedding 服務範例
resources/     Runtime resources 範本（bge-m3）
```
