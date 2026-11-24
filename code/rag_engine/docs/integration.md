# 接上公司資源

這份文件說明要提供哪些外部資源（ES、Embedding、LLM）、設定寫在哪裡，以及怎麼確認接通。程式已在記憶體索引與 hash 向量上測過完整流程；接上真實服務後，先依本文件驗證，再部署 DEV Runtime。

## 取得程式碼

clone 整個 rag_platform repo，切到 `docs/rag-system-factory`，在 `code/rag_engine` 內工作。規格在 `../../docs`，`make sync-contracts` 預設也從 `../..` 同步契約。若把 rag_engine 搬到獨立 repo，旁邊要保留一份 rag_platform，同步時加 `PLATFORM=<rag_platform 路徑>`。

## 需要的資源

| 資源 | 必要性 | 要提供什麼 | 設定位置 |
|---|---|---|---|
| Elasticsearch 8.19（Builder 測試用 `dev_test`） | 必要 | 位址、Basic 帳密、CA 憑證（自簽時）。叢集要裝 `analysis-ik` 與 `analysis-stconvert`（`analysis-smartcn` 為備案） | `RAG_ES_URL`、`RAG_ES_USERNAME`、`RAG_ES_PASSWORD`、`RAG_ES_CA_CERTS`、`RAG_ES_VERIFY_CERTS` |
| PLED ES 位址規則 | 有 System 選 PLED ES 時才需要 | 由 `es_number` 組出位址的樣板；帳密由該 System 的 Config Secret 提供 | `RAG_PLED_ES_URL_TEMPLATE`，例如 `https://es{es_number}.pled.example:9200` |
| bge-m3 Embedding 服務 | 必要 | OpenAI 相容的 `POST {endpoint}/embeddings`，回 1024 維；需要時提供 Token | resources 檔的 `profiles.bge-m3`（`endpoint`、`request_model`、`model_revision`、`api_key_env`） |
| bge-m3 `tokenizer.json` | 必要 | 與服務上模型同一個 commit 的檔案 | 放在 `models/bge-m3/tokenizer.json`（建 Image 時放進 `/opt/models/bge-m3/`）；resources 檔的 `tokenizer_profiles.bge-m3` |
| 公司 LLM 服務 | System 用 Rewrite 時必要 | OpenAI 相容的 `POST {endpoint}/chat/completions`，要支援 `response_format` 的 `json_schema`；需要時提供 Token | resources 檔的 `models.<id>`（`label`、`endpoint`、`request_model`、`api_key_env`、`timeout_seconds`、`temperature`）。使用者在 Builder 只選 ID（`llm_ref`），Token 放部署的 Secret |
| PyPI 映像、base image、CI | 建置用 | 公司內部來源 | 見 `docs/tech_stack.md` 末表 |

Remote API 節點呼叫的是使用者自己的服務，網址與 Token 寫在各 System 的 Config，不屬於 Runtime 的部署資源。Rerank `model_api` 尚未實作，目前不需要 Rerank 服務。

### 介面要求

**Embedding 服務**：Runtime 送 `{"model": <request_model>, "input": [<文字>, ...]}`，期待回 `{"data": [{"index": 0, "embedding": [...]}, ...]}`，每筆維度等於 profile 的 `dimensions`。TEI、vLLM、Infinity 都是這個格式。設了 `api_key_env` 時，Runtime 從該環境變數取 Token，以 `Authorization: Bearer <token>` 送出；變數為空時 Runtime 不啟動。公司服務格式或認證方式不同時，只需要改 `src/rag_engine/adapters/embedding.py`。

**LLM 服務**（規則見 rag_platform 03#rewrite-rules、06#llm-service-deployment）：Runtime 送 `model`（`request_model`，沒填就用 ID）、`messages`（平台的 system 訊息＋使用者 Prompt）、`temperature`，以及 `response_format: {"type": "json_schema", "json_schema": {"name": "rewrite_queries", "strict": true, "schema": ...}}`；期待回 `choices[0].message.content` 為 `{"queries": [...]}`。Token 的做法與 Embedding 相同（`api_key_env`）。服務格式或認證方式不同時，只需要改 `src/rag_engine/adapters/llm.py`。

**Elasticsearch**：目前只支援 Basic 帳密。若公司 ES 用 API Key 或其他方式認證，改 `src/rag_engine/runtime/stores.py` 的 `_elasticsearch`（elasticsearch-py 的 `api_key` 參數）。

## 步驟一：本機接上（不部署）

1. 把 `tokenizer.json` 放到 `models/bge-m3/tokenizer.json`。
2. 複製 `resources/dev.yaml` 成 `resources/local.yaml`，填入：
   - `profiles.bge-m3.endpoint`：Embedding 服務的 base URL，例如 `http://bge-m3.internal/v1`。
   - `model_revision`：模型 commit。
   - `tokenizer_profiles.bge-m3.path`：本機路徑 `models/bge-m3/tokenizer.json`。
   - `tokenizer_profiles.bge-m3.revision`：`bge-m3@<commit>`。
   - 服務需要 Token 時，加上 `api_key_env: RAG_EMBEDDING_API_KEY`。
   - 要用 Rewrite 時，`models.default-llm` 填 `endpoint`、`request_model`，需要 Token 時設 `api_key_env: RAG_LLM_API_KEY`。ID 用 `default-llm` 與 Descriptor 的預設值一致，也可以列多個模型。
3. 先單獨驗證 ES、Embedding 與 LLM：

```bash
RAG_TEST_ES_URL=https://... RAG_TEST_ES_USERNAME=... RAG_TEST_ES_PASSWORD=... make test-es
```

```bash
curl -s -H "Authorization: Bearer $RAG_EMBEDDING_API_KEY" -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": ["測試"]}' http://bge-m3.internal/v1/embeddings | head -c 300
```

```bash
curl -s -H "Authorization: Bearer $RAG_LLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"model": "<request_model>", "messages": [{"role": "user", "content": "把「散熱孔怎麼清潔」改寫成 2 個檢索問題"}], "response_format": {"type": "json_schema", "json_schema": {"name": "rewrite_queries", "strict": true, "schema": {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2}}, "required": ["queries"], "additionalProperties": false}}}}' \
  http://llm.internal/v1/chat/completions
```

4. 啟動接上真實服務的 Runtime（有設 `api_key_env` 時，對應的環境變數也要帶上）：

```bash
RAG_MANAGEMENT_USERNAME=mock RAG_MANAGEMENT_PASSWORD=mock \
RAG_RESOURCES_FILE=resources/local.yaml \
RAG_INDEX_BACKEND=elasticsearch RAG_EMBEDDING_BACKEND=service \
RAG_ES_URL=https://... RAG_ES_USERNAME=... RAG_ES_PASSWORD=... \
uv run python -m rag_engine.runtime
```

5. 另開終端機跑完整流程。腳本取 Catalog 的第一個 Profile 與 Tokenizer，用 `dev_test` 建索引，結束時刪除。加 `SMOKE_ARGS=--rewrite` 會再切換成 Rewrite（用 Catalog 第一個模型）並查詢一次，印出改寫結果：

```bash
make smoke SMOKE_ARGS=--rewrite
```

## 步驟二：部署 DEV Runtime

1. 建 Image：`make image`（需要 `models/bge-m3/tokenizer.json`；Dockerfile 的 `PYTHON_IMAGE`、`UV_IMAGE` 可改成公司映像）。
2. 改 `deploy/k8s/dev-runtime.yaml`：namespace、image、ES 位址、`RAG_PLED_ES_URL_TEMPLATE`、ConfigMap 內的 resources（同步驟一），建立 `dev-runtime-es`、`dev-runtime-management`、`dev-runtime-llm` 三個 Secret（LLM 不需要 Token 時，刪掉 `api_key_env` 與 `RAG_LLM_API_KEY`）；Embedding 需要 Token 時，打開檔案中註解掉的 `RAG_EMBEDDING_API_KEY`。FTEST／ENT 的 Runtime 若承載使用 Rewrite 的 System，部署也要列出同一個模型並提供 LLM Secret。
3. Istio 與 Gateway 依 rag_platform `examples/system_config/deployment.istio-http.example.yaml`。
4. 驗收：

```bash
RAG_SMOKE_MANAGEMENT_USERNAME=... RAG_SMOKE_MANAGEMENT_PASSWORD=... make smoke URL=https://<DEV Runtime> SMOKE_ARGS=--rewrite
```

## 第一次接上時可能遇到的問題

下列項目在開發環境無法驗證，第一次接上時優先檢查。

| 症狀 | 可能原因 | 處理 |
|---|---|---|
| 建索引失敗，訊息提到 `stconvert`、`ik_max_word` | ES 沒裝外掛 | 裝外掛（版本須與 ES 相同）。暫時可把 resources 的 `text_analysis` 改成 `standard`，但這會改變索引指紋，正式環境不要混用 |
| 已發布的 System 做 reload／update 時被判定索引不相容 | ES 讀回的 mapping 補了預設值，`mapping_compatible` 比對方向有誤 | 看 `runtime/systems.py` 的 `mapping_compatible`，roadmap R1 第 2 點 |
| 匯入失敗：`embedding service returned unexpected vectors` | 維度不是 1024，或回應格式不同 | 檢查 profile 的 `dimensions` 與服務回應；格式不同就改 `adapters/embedding.py` |
| 匯入失敗：`embedding service returned HTTP 401` | 沒設或設錯 Token | `api_key_env` 與對應環境變數 |
| 啟動失敗：`environment variable ... is empty` | 設了 `api_key_env`，但環境變數沒值 | 提供該環境變數 |
| 啟動或匯入失敗，找不到 tokenizer | `tokenizer_profiles` 的 `path` 錯誤 | 本機用 repo 內路徑，Image 內是 `/opt/models/bge-m3/tokenizer.json` |
| 匯入失敗：`EMBEDDING_INPUT_TOO_LONG` | 單塊超過模型上限 | 調小 Chunking 的 `max_tokens`；切分規則見 rag_platform 03#chunk-token-rules |
| ES 連線 TLS 錯誤 | 公司自簽 CA | `RAG_ES_CA_CERTS` 指向 CA 檔，或把 CA 裝進 Image |
| Rewrite 查詢回 `502 UPSTREAM_ERROR`（`module: query_transformation`），訊息是 `LLM service returned HTTP 400` | LLM 服務不接受 `response_format` 的 `json_schema`，或不接受 `minItems`／`maxItems` | 先用步驟一的 curl 確認。規格要求不能默默換成較弱的模式；若服務只支援 `json_object`，在 resources 的模型設定加一個輸出模式選項並改 `adapters/llm.py`，回應仍由 `components/rewrite.py` 嚴格驗證 |
| Rewrite 查詢成功，但 `query_variants` 只有原始問題；Log 有 `rewrite fell back to the original query`（`code: REWRITE_FALLBACK`，`status` 是原因） | 模型回答兩次都不合格式、拒答或被截斷 | 用 curl 看模型實際輸出；調整 Prompt 或換模型 |
| 啟動失敗：`model default-llm: environment variable RAG_LLM_API_KEY is empty` | 設了 `api_key_env`，但沒有提供 Token | 提供 Secret，或該服務不需要 Token 時刪掉 `api_key_env` |
| Fixed-size／Header-aware 的切點與預期不同 | bge-m3 tokenizer 的 Token 位置與測試 tokenizer 不同 | 屬預期差異；用 bge-m3 實測後補測試（roadmap R2） |

## 不要自行決定的項目

以下項目規格尚未定案，實作前先在 rag_platform 提出並確認，不要在 Runtime 自行補語意：`content` 來源與檔案 Parser（Q-005）、Rerank `model_api` 與其服務契約（Q-003）、Remote 多 Query 合併（Q-014／Q-028）、`preserve_original`／`include_original_chunk`（D-53）、FTEST／ENT 首次建索引、SIGTERM 優雅關閉。清單與狀態見 [roadmap.md](roadmap.md) 的 R4。
