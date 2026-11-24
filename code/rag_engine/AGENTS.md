# 給開發 Agent 的說明

這個目錄是 Retrieval Runtime（rag_engine）。規格在 rag_platform 的 `docs/`：放在 rag_platform 的 `code/rag_engine/` 時就是 `../../docs/`；搬到公司內部 repo 後指向對應的 rag_platform。本目錄的 `docs/` 只記錄實作。開始前依序讀：

1. `docs/tech_stack.md`：技術選型與理由，不要換掉已定的框架。
2. `docs/architecture.md`：分層、模組責任與不可破壞的規則。
3. `docs/roadmap.md`：目前狀態、下一步與已知缺口。

## 工作規則

- 遵守 KISS：先寫最簡單、能讀懂的版本。優先用一般函式、`if`／`for` 與 dataclass；不要為了少幾行而用 walrus、metaclass、自訂 decorator、泛型、動態產生函式或過度抽象。效能或擴充需求真的出現時再改，並在 `docs/roadmap.md` 記錄原因。
- 併行只用單程序 asyncio。不要加 `asyncio.to_thread`、執行緒池或多程序 Worker；需要時先在 roadmap 提出，經確認後再做。
- 每次修改後執行 `make check`（ruff、mypy、import-linter、pytest），全部通過才算完成。新行為要有測試。
- HTTP 回應形狀以 `src/rag_engine/contracts/data/schemas/runtime_http.schema.json` 為準；測試用 `validate_http(...)` 驗證每個回應。
- `src/rag_engine/contracts/data/` 不可手改。規格變更時先改 rag_platform，再執行 `make sync-contracts`（在 rag_platform 內預設取 `../..`，其他位置加 `PLATFORM=<rag_platform 路徑>`）。
- Runtime 一個 Pod 只能跑一個程序。不要加 gunicorn、多 worker 或跨程序共享狀態。
- `runtime/ingestion.py` 中修改占用、Queue、Run 狀態的程式碼不能有 `await`。
- LangGraph 節點之間傳值只能放在 state。每個節點拿到的 `config["configurable"]` 是副本，在節點內寫入後面的節點看不到；它只放呼叫端傳入的唯讀值。
- 會影響索引內容的設定一定要進 `engine/compiler.py` 的指紋投影；純查詢參數不能進。
- 錯誤一律用 `ApiError`（runtime）或 `EngineError` 子類（engine 以下），代碼要在 rag_platform 06 的錯誤表中。
- Log 不得含 Secret 值、`Authorization` 或文件原文全文。

## 常用指令

```bash
make install        # uv sync
make check          # 全部檢查
make run            # 本機示範：記憶體索引＋hash 向量＋測試資源，帳密 mock/mock
make test-es        # 需要 RAG_TEST_ES_URL，對真實 ES 驗證
make smoke          # 對啟動中的 Runtime 走完整流程（預設 http://127.0.0.1:8080，可加 URL=...）
```

測試分層與換成公司環境的做法見 `docs/testing.md`。

## 新增一個內建 Component

1. 在 `components/` 寫純函式實作與單元測試。
2. 在 `engine/compiler.py` 加參數驗證、欄位推導與指紋投影；需要新的計畫型別時加在 `engine/plan.py`；在 `engine/pipelines.py` 的 `run_ingestion_stage` 或查詢節點接上。
3. 在 `engine/catalog.py` 的 `IMPLEMENTED` 加入 `(module, component_id, version)`。Descriptor 必須已存在於 rag_platform 的 Descriptor registry（`examples/system_config/builder_form.descriptors.json`，同步後為 `contracts/data/catalog/descriptors.json`）。
4. 補一個走 HTTP 的流程測試。
