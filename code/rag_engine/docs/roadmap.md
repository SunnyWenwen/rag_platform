# 交接狀態與後續工作

## 目前狀態

| 範圍 | 狀態 | 證據 |
|---|---|---|
| 17 個 DEV HTTP 操作、MCP、Health | 已實作 | `tests/test_runtime_flow.py`、`tests/test_mcp.py`（官方 MCP client 實測） |
| Basic 認證、`X-Request-Id`、錯誤格式 | 已實作 | 同上，所有回應以 `runtime_http.schema.json` 驗證 |
| 生命週期：initialize、reload、update（沿用／重建）、recover_index、detach、DELETE、Idempotency-Key、STALE_CONTEXT | 已實作（記憶體索引） | `test_runtime_flow.py` |
| Pod 內匯入控制：占用、整批衝突、Queue、取消含 `cancelling`、Bulk 逾時、保留期 | 已實作 | `tests/test_ingestion_control.py` |
| Config 編譯與索引指紋 | 已實作 | 與 rag_platform 指紋範例的投影及摘要完全一致 |
| Recursive 切分、Dense Embedding、RRF／Sum、group_by、跨 Query 合併、Filter | 已實作 | `tests/test_engine_units.py` |
| Remote API Adapter 與 Remote Ingestion | 已實作 | `tests/test_remote_and_embedding.py`（MockTransport） |
| `ElasticsearchIndexStore` | **已寫、未對真實叢集驗證** | 只有假 client 的請求形狀測試；實機測試 `tests/test_es_store.py -m es` 待跑 |
| bge-m3 Embedding client、HF Tokenizer 載入 | **已寫、未對真實服務驗證** | MockTransport 測試 |

## 建議順序

每項完成時執行 `make check`，並補上對應測試。

### R0 公司環境

套上公司的 Python 版本、PyPI 映像、base image 與 CI（見 `docs/tech_stack.md` 末表）。驗收：乾淨環境 `make install && make check` 通過。

### R1 PLED 測試 ES

1. 設定 `RAG_TEST_ES_URL`、帳密，執行 `make test-es`。確認 IK＋stconvert 分析器建立成功、簡體查詢命中繁體內容、`int8_hnsw` kNN 與 Filter 可用。
2. 檢查 `runtime/systems.py` 的 `mapping_compatible`：ES 讀回的 mapping 可能補上預設值（例如 `index_options` 的 `m`、`ef_construction`），確認比對方向正確，不會誤判。
3. 用 `RAG_INDEX_BACKEND=elasticsearch` 啟動 Runtime，重跑 `tests/test_runtime_flow.py` 的流程（可把 fixture 的 settings 換成 ES）。

### R2 bge-m3

1. 部署 Embedding 服務（例如 `deploy/k8s/bge-m3-embedding.example.yaml` 的 TEI），確認 `/v1/embeddings` 回 1024 維。
2. 把 `tokenizer.json` 放到 `models/bge-m3/`，`resources/dev.yaml` 填入同一個 commit。
3. 新增 `-m embedding` 實機測試：同一句話的 Query 向量與文件向量 cosine 接近 1，長度超過 8192 token 會回 `EMBEDDING_INPUT_TOO_LONG`。

### R3 DEV 上線

1. 建 Image、套 `deploy/k8s/dev-runtime.yaml`，接 Istio 與 Gateway（見 rag_platform `examples/system_config/deployment.istio-http.example.yaml`）。
2. 讓 rag_platform 的 `examples/system_config/test_runtime_http_contract.py` 可以改打真實 Runtime：只驗 Schema、OpenAPI 與狀態轉移，不比對 Mock 的固定 body。
3. 和外包 Builder 一起跑 Catalog → 預檢 → 發布 → 匯入 → 查詢 → 取消 → 卸載。

### R4 功能缺口（依里程碑）

| 缺口 | 里程碑 | 備註 |
|---|---|---|
| 內建 Inference 參數的 `{{KEY}}` 取值 | M1 | 目前編譯時拒絕，見 05#parameter-references |
| `content` 來源與檔案 Parser | M2 | Q-005；目前只有 `passthrough` |
| Fixed-size、Header-aware 切分；`preserve_original`、`include_original_chunk` | M2 | 目前編譯時拒絕 |
| Rewrite（LLM）與 Rerank `model_api` | M2 | Catalog 尚未列出 |
| Remote Query Transformation 產生多 Query 後的平台合併設定 | M2 | Q-014／Q-028，目前用預設合併 |
| FTEST／ENT 首次建立索引的指令 | M7 | rag_platform `docs/todo_enhance.md#standalone-index-initialization` |
| SIGTERM 優雅關閉 | 後續 | `todo_enhance.md#runtime-graceful-shutdown` |
| Readiness 檢查 ES 連線、OpenTelemetry | M3 | |
| 未載入 System 的 GET 查核只查 `dev_test` 叢集 | M3 | PLED 叢集的位址需要 Config，未載入時無從得知 |

## 已回寫 rag_platform 的實作決定

以下四點已在 rag_platform `docs/rag-system-factory`（commit `83e0ac1`）更新，本 repo 的契約複本已同步：

1. 索引 mapping 以 `{"type": "object", "enabled": false}` 保存 `metadata`，指紋範例同步更新。
2. MCP 錯誤結果只回 `content` 文字（`CODE: message`）與 `isError: true`，不帶 `structuredContent`。
3. Runtime 的 `separators` 預設為 `["\n\n", "\n", " ", ""]`；Builder 對中文內容預填含 `。！？；` 的分隔符。
4. `catalog_revision` 由 Descriptor 與 resources 內容計算，格式為 `catalog-<hash>`。
