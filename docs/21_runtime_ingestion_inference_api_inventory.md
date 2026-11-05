# 21 — Runtime Ingestion／Inference API 盤點草案

更新日期：2026-11-05。適用 A～E 中的執行契約、System 組裝與環境控制；總盤點見 [20](20_contract_inventory_responsibility_matrix.md)。

**文件分成「已確認行為」與「本次建議 API／回應格式」。**本次盤點不代表 OpenAPI、所有 HTTP code／欄位或新增功能已核定，也沒有實作 Runtime、修改共用資料 Schema 或 UI。決策由 [08 的 D-56／相關 Q-ID](08_implementation_plan.md) 追蹤。

## 1. 範圍與已確認基準

### 1.1 這份清單是哪一層

這裡盤點 **Retrieval Runtime 對外的業務 API**：Builder DEV 與自行部署到 FTEST／ENT 使用同一語意與實作，各環境以 E 設定限制。Builder DEV 的可信路由先選定 System；獨立 Runtime 綁定既定 System。不把 system_id／tenant 任意覆寫放進業務 JSON。

以下不是本文件的新增範圍：Builder Workspace／System CRUD、Config／Component 目錄管理、Export、AI 助手、Evaluation，以及 Developer Remote Service 的 operation HTTP 協定。後者引用 [18](18_remote_service_pipeline_integration.md)，不是將每個 Module 都公開成 Runtime API。

Library 仍可直接由 Python 使用；本表描述 Runtime HTTP／工作管理層，不要求每次 Library 呼叫都經 HTTP。

### 1.2 已確認，不再當成待選方向

- 同一 System 的同一 document_id 以新文件完整替換；不存在則新增，成功後移除該文件不再產出的舊 Chunk。
- 更新與執行結果以 document_id 為單位。Batch 中不同文件獨立成功／失敗，不要求全 Batch 回滾；失敗不發布半份新版，維持最後成功版本。索引實際發布／崩潰一致性仍需後端與 Remote Service 配合驗證。
- 不保存斷點續跑；重試整份文件。Runtime 重啟不恢復已接受的排隊／執行工作。
- Runtime 統一管理有上限的 Ingestion Queue、併發、Inference Rate limit／併發與逾時。每 System 的文件執行併發可配置，預設 1；調高前需驗證 Component／共享資源安全，不等於無限制並行。
- 同一 System 的同一 document_id 已 queued／running 時，拒絕再次提交；終態後才可重新提交覆寫。不同文件可依上限並行；Batch 是文件集合，不是另一種資料契約。
- Runtime 額外保存文件級工作紀錄於記憶體，不放入 IngestionDocument／ParsedDocument／Chunk，也不從既有索引反推執行狀態；重啟後查不到的狀態為 unknown。
- 202 表示已接受排隊，不表示解析、Embedding、索引或可搜尋已成功；提交後須可查詢結果。
- Inference 沿用 query／filters／metadata 輸入，同步回 QueryContext[]；不做 Generation，不因非同步 Ingestion 而新增 InferenceState。

## 2. 建議第一版：5 支業務 API＋2 支 Health API

路徑、Header 與 Envelope 為本輪提案；既有單筆 IngestionDocument 與 QueryContext 契約維持。P0 表示建議納入最小交付，不表示已實作。

| 優先 | Method／Path 草案 | 用途 | Request | 成功回應草案 | 主要行為 |
|---|---|---|---|---|---|
| P0 | POST /v1/ingestions | 提交單份文件 | 一份既有 IngestionDocument | 202：run_id、queued、config_revision、文件清單；Location 指向工作查詢 | 預檢與容量檢查通過、入列及紀錄建立完成後接受；API body 仍與單筆 Parser input 相同 |
| P0 | POST /v1/ingestions:batch | 提交多份文件 | {documents: IngestionDocument[]} | 202：同一 run_id 對應多份文件 | 每筆仍驗證同一份 IngestionDocument，逐文件執行／更新；批次入列前拒絕政策見討論項 API-D01 |
| P0 | GET /v1/ingestions/{run_id} | 查一次提交的整體及逐文件結果 | run_id | 200：Run 狀態、文件計數、逐文件狀態／錯誤 | run_id 僅是一次提交的追蹤 ID；Batch 不另造另一種任務 ID |
| P0 | GET /v1/documents/{document_id}/ingestion-status | 只知道文件 ID 時查最近一次狀態 | document_id | 200：最近一次 run_id、status、目前 Module、時間與錯誤 | 只查已授權 System；不是文件內容／存在性查詢；無紀錄回 unknown 的 HTTP 表達為本輪建議 |
| P0 | POST /v1/queries | 執行設定好的 Query Transformation／Retrieval／Rerank | {query, filters?, metadata?} | 200：根層直接 QueryContext[] | 同步完成；Rate limit、執行併發與 Deadline 由 Runtime 管理，不走 Ingestion 長工作 Queue |
| P0 支援 | GET /health/live | 檢查 Runtime 程序存活 | — | 200：存活 | 不依是否有資料判斷；對外暴露範圍依部署政策 |
| P0 支援 | GET /health/ready | 檢查 Runtime／必要依賴是否可接收操作 | — | 200：初始化／必要依賴就緒；否則 503 | 不把「尚無可查索引」一律當成不 Ready，否則空 System 無法正常接收 Ingestion |

共享 Builder DEV 的多 System 路由／各 System 就緒狀態須由可信管理層區分；Pod 的 Health 不能代替任意 System 的 Query-ready。精確路由、授權及能力接口仍見 07／Q-019／Q-020。

## 3. Ingestion 的提交與接收

### 3.1 單筆保持既有輸入

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "content": {"text": "設備每月需清潔散熱孔。", "title": "保養規範"},
  "metadata": {"department": "manufacturing"}
}
```

content／base64／uri 三選一及其他合法欄位引用 [13](13_ingestion_parser_input_contract.md) 與共用 [Schema](../schemas/ingestion_document.schema.json)。Batch 包裝只屬 Runtime 接收層；Parser 每次收到的仍是單份 IngestionDocument，不收到 documents 容器或 run_id。

### 3.2 Batch 包裝提案

```json
{
  "documents": [
    {"document_id": "manual-001", "content": {"text": "設備每月需清潔散熱孔。"}},
    {"document_id": "manual-002", "content": {"text": "每週清潔濾網並記錄保養結果。"}}
  ]
}
```

建議使用獨立 Batch 端點，保持原本「單筆 API body＝Parser input」的承諾；不要求單筆也套 documents wrapper。是否採此路徑／包裝列 API-D01。

### 3.3 202 回應提案

Location: /v1/ingestions/ing-001

```json
{
  "run_id": "ing-001",
  "status": "queued",
  "config_revision": "C1-example",
  "documents": [
    {"document_id": "manual-001", "status": "queued"},
    {"document_id": "manual-002", "status": "queued"}
  ]
}
```

單筆提交也使用相同 receipt，只含一筆 documents；不改動輸入契約。Receipt 是接受當下的快照，Client 查詢時可能已 running 或完成。

建議接收階段只做授權、JSON／外層 Schema、有效 Config／Parser 能力等快速預檢、文件忙碌檢查與容量預留。下載、昂貴 Parsing、Embedding／Indexing 在 Worker 執行，失敗由狀態 API 回報，不能把 202 當作最後成功。

**Batch 建議採「預檢整批通過才入列；入列後逐文件獨立結果」。**例如外層不合法、同批重複 ID、某文件已 queued／running、容量不足時，先拒絕整次請求，保證沒有未交代的部分入列；這是 API-D01 提案，尚未核定。合法文件入列後，另一份文件 Parsing 失敗不回滾已成功文件。

併發與 Queue 容量建議以文件工作計數，並另限制排隊資料量／總請求大小，避免一個巨大 Batch 算一個 queue slot。具體數值、接收容量預留及公平排程見 API-D04。預留文件忙碌標記、Queue 容量與狀態紀錄須一致，不能檢查後因競態收進同文件兩份工作。

## 4. 文件狀態與一次提交的狀態

### 4.1 文件級狀態

| status | 定義 |
|---|---|
| queued | 已接受，等待執行 |
| running | 正在處理；module 可提供目前邊界 |
| completed | 該文件完整處理、替換與索引發布完成；不是剛取得模型回應或只送出索引寫入 |
| failed | 已知處理失敗，附可定位錯誤；不續跑半份文件 |
| unknown | 沒有可用工作紀錄，或執行結果無法確認；不等於文件不存在／未寫入／失敗 |

unknown 的兩種原因需可區分：一是重啟／到期後已無紀錄；二是 Remote timeout 等造成提交結果未確認。後者若尚有紀錄應帶 error code，不能將「不知道是否寫入」偽裝為確定失敗可安全重送。具體 code 與再次提交前如何確認／隔離，列 API-D05。

module 可為 null（例如 queued 或終態），亦可指目前 Local Module 或 Remote operation 的可知邊界；不假造 Remote 私有流程內部的百分比。error 在沒有錯誤時為 null，失敗時使用 code／module／message 等受控內容，不公開 Stack／Secret。

```json
{
  "document_id": "manual-001",
  "run_id": "ing-001",
  "status": "running",
  "module": "Embedding",
  "updated_at": "2026-11-05T08:30:00+08:00",
  "error": null
}
```

重啟或紀錄已清除的回應提案：

```json
{
  "document_id": "manual-001",
  "run_id": null,
  "status": "unknown",
  "module": null,
  "updated_at": null,
  "error": null
}
```

### 4.2 Run 是一次接收，文件是更新單位

文件最新狀態索引以可信的 (System, document_id) 對應最近一次 run_id；每次合法重新提交建立新 run_id，先前 Run 的結果在保留期內仍能查，不被文件最新狀態覆寫。這不要求持久儲存完整執行歷史。

Batch 彙總狀態建議：仍有 running 為 running，只有等待且尚無終態為 queued；已處理部分且還有待處理文件時為 running；全成功為 completed、全失敗為 failed、已全部終結但有成功亦有失敗為 partial。**partial 只適用 Run 彙總，不適用半份文件發布。**沒有活躍工作但至少一筆結果未確認時，Run 建議為 unknown，不偽裝為全失敗或已確認 partial。名稱／彙總規則列 API-D02。

```json
{
  "run_id": "ing-001",
  "status": "partial",
  "config_revision": "C1-example",
  "counts": {"total": 2, "queued": 0, "running": 0, "completed": 1, "failed": 1, "unknown": 0},
  "documents": [
    {"document_id": "manual-001", "status": "completed", "module": null, "updated_at": "2026-11-05T08:31:00+08:00", "error": null},
    {"document_id": "manual-002", "status": "failed", "module": "Parsing", "updated_at": "2026-11-05T08:30:30+08:00", "error": {"code": "PARSER_CONTENT_INVALID", "module": "Parsing", "message": "內容不符合所選 Parser 的輸入要求。"}}
  ]
}
```

counts 指這次接收的 IngestionDocument 數，不是 Unit／Chunk／模型呼叫次數；大文件不偽造固定完成百分比。分頁／批次大小上限應一起決定，避免無界狀態回應。Run 失去紀錄時建議只回 run_id／status=unknown，不填 0 個文件冒充空 Batch。

### 4.3 紀錄的保存與重啟

- 由 Runtime 記憶體保存 Queue、Run／逐文件狀態，以及 document_id 的最新 Run 對照；不新增必要 DB。
- 僅完成／失敗等可回收紀錄依保留時間／數量清理，不能因 TTL 提前刪除活躍工作；未確認結果的紀錄需依 API-D05 處理。具體保留值列 API-D04。
- Runtime 重啟後不恢復 Queue／工作／狀態。已接受但未完成的工作可能遺失；202 不承諾跨重啟完成。
- 狀態清空不保證 ES／MongoDB／Remote Service 也回滾。既有持久資料或仍在執行的 External 呼叫須按實際結果確認，不能從「查不到 Run」推定沒有副作用。
- Memory 索引重啟遺失仍依既定政策重新 Ingestion；ES／MongoDB 的資料恢復與工作續跑是兩件事。
- 初期單實例／同程序規劃沿用 07。若增加多 API replica／worker process，記憶體 Queue／狀態不會自然共用，需另定路由或共享控制，不在此次承諾。

## 5. Inference

### 5.1 Request 與結果

```json
{"query": "設備多久需要清潔？", "filters": [{"field": "metadata.department", "operator": "eq", "value": "manufacturing"}], "metadata": {"language": "zh-TW"}}
```

query 必填；filters／metadata 選填，預設 []／{}，沿用 [05](05_data_contracts_search_design.md)／[07](07_backend_runtime_integration.md)。Runtime 結合可信 System／ACL Filter，初始化 QueryContext[]，依所選 Component 執行。Metadata 不是任意 Config／授權覆寫入口。

成功 body 根層仍是 **QueryContext[]**，不另包 run_id、data、answer 或 InferenceState；完整範例引用 [07 §5.6](07_backend_runtime_integration.md)／[17](17_pydantic_contracts_draft.md)。沒有命中是成功空候選，與索引不就緒／服務失敗分開。

### 5.2 執行與流量

每 System 配置請求頻率、執行併發、等待／執行 Deadline；Runtime 再控制共享資源總量。Builder 可額外限制 User／Workspace 的平台測試配額。共用 Runtime 的限制不能只寫在前端。

第一版採同步查詢，額滿直接拒絕或僅允許有上限的短等待；精確行為列 API-D04，不把查詢塞進 Ingestion 的長工作 Queue。實際 Rate／併發數由 E 設定，不放在每次 query body，也不因換環境改寫 D 的搜尋邏輯。

目前不需要另開 async Query／查詢工作狀態 API，也不增加獨立 Rewrite／Retrieval／Rerank 測試端點；後者需有明確需求再討論，既有 UIB-007／008 仍未核定。

## 6. HTTP、狀態與錯誤層次提案

| 情境 | 建議 HTTP／行為 |
|---|---|
| JSON 不可解析 | 400，未接受工作 |
| 授權缺失／不足 | 401／403，適用提交與所有狀態查詢 |
| Request body 超過限制 | 413，未接受工作 |
| 外層 Schema 不合法／同 Batch 重複 document_id | 422，附位置；批次整批拒絕為 API-D01 提案 |
| 同 System 的 document_id 已 queued／running | 409，附目前 run_id 或可查狀態；不建立第二份工作 |
| System／使用者的請求速率或接收配額已滿 | 429，附可用的 Retry-After／錯誤原因；不回 202 |
| Runtime 不就緒／整體容量無法接收／Query 索引不就緒 | 503，使用可區別的 code；接收容量與 Query index-ready 分開 |
| 已成功接收 Ingestion | 202＋run_id／Location；尚未成功完成 |
| 202 之後的文件執行失敗 | 狀態 GET 仍為 200，文件 status=failed 與 error；不是將原 POST 改回 HTTP 500 |
| 狀態紀錄遺失／到期 | 建議狀態 GET 200＋unknown；不宣稱文件不存在，列 API-D02 |
| Query 成功但無命中 | 200＋QueryContext[] 中的空候選 |
| Query 執行／上游 API 失敗或超時 | 依錯誤來源映射 5xx（502／503／504 等）與 code；不偽造成功結果 |

輸入預檢拒絕、工作執行失敗、索引可見性、狀態查不到是不同問題。錯誤碼與數值上限尚未完整核定，不能把這張表當成完整 OpenAPI。

202／狀態監看依據：[RFC 9110 §15.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)；429／Retry-After 依據：[RFC 6585 §4](https://www.rfc-editor.org/rfc/rfc6585.html#section-4)。RFC 支持 HTTP 語意，不替本專案決定 Queue 耐久性、批次政策或錯誤 Envelope。

## 7. 非必備端點與本輪待討論

### 7.1 先列需求，不加入最小 7 支

| 能力／候選 API | 本次建議 | 還需定義什麼 |
|---|---|---|
| DELETE /v1/documents/{document_id} | 若第一版需刪除資料再納入，不因支援覆寫就自動加入 | 忙碌時是否拒絕、刪除索引／文件／狀態範圍、Remote 支援及同步／非同步 |
| POST /v1/ingestions/{run_id}:cancel | 先延後 | queued／running 的取消邊界、Remote 停止能力、已提交文件不回滾、狀態 |
| 文件列表／內容／Chunk 查詢 | 先延後，與工作狀態分開 | 分頁、投影、權限、所有儲存／Remote 模式是否可提供 |
| 索引詳細狀態／容量資訊 | 可作後續管理診斷能力 | System index-ready／恢復狀態、統計來源與成本；不能只靠 Health 或最近一次 Run 推斷 |
| Rewrite／Rerank 單步測試、async Inference／streaming | 目前不納入 | 獨立需求、I/O、成本與正式範圍；不重新引入 Generation |

### 7.2 建議逐項確認的決策

| ID | 尚需確認 | 建議起點 | 關聯 |
|---|---|---|---|
| API-D01 | Batch 路徑／容器與入列前部分接收政策 | 單筆維持原格式；Batch 獨立端點＋documents[]；預檢整批通過才入列，之後逐文件獨立結果 | Q-019／Q-009 |
| API-D02 | Run 彙總狀態／回應格式及未知狀態 HTTP | 文件無 partial；Run 可 partial；狀態紀錄不見回 200＋unknown；保留 run_id 與 document_id 兩種查詢 | Q-019／Q-017 |
| API-D03 | 文件刪除／工作取消是否首期必要 | 第一版先不開取消；刪除依實際使用需求決定；不要求完整文件 CRUD | Q-008／Q-017 |
| API-D04 | 併發／容量／保留時間／Deadline 的具體值與排程 | 文件併發預設 1 且可調；Queue 依文件數與資料量設限；終態紀錄有限保留；Inference 先不長時間排隊 | Q-017／Q-020／Q-027 |
| API-D05 | Remote 結果不明、索引發布、Config 改變時的工作／Query 行為 | 不自動重試未知寫入；提交固定當次 config_revision；活躍工作期間先限制不相容 Config 變更；文件發布由後端明確實作 | Q-008～010／Q-015／Q-017／Q-028 |
| API-D06 | 對外認證與共享 Runtime 的 System 路由 | 遵循企業 Gateway／Token 規範，所有提交／查詢都驗證 System 權限；Health 暴露另設；不接受任意 Header 覆寫租戶 | Q-006／Q-019／Q-020 |

API-D01～06 是本文件的盤點子項，沿用現有 Q-ID，不宣稱新增 API 已定案。完整 JSON Schema／OpenAPI、錯誤碼、ID 編碼與協定版本在此基礎上再凍結。單筆文件忙碌拒絕、重啟不恢復、文件級記憶體狀態與 Inference 流量控制等已確認方向，不重新列為選擇題。

驗收先採：單筆／Batch 接收、文件忙碌衝突、Queue 滿、逐文件 partial、狀態兩種查詢、重啟 unknown、同 ID 完整替換、Query 無命中／不就緒／限流，以及已授權 System 隔離。這些是未來實作驗收清單，不是本文件新增的可執行測試。
