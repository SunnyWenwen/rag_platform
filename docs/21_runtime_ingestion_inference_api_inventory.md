# 21 — Runtime Ingestion／Inference API 盤點草案

更新日期：2026-11-05。適用 A～E 中的執行契約、System 組裝與環境控制；總盤點見 [20](20_contract_inventory_responsibility_matrix.md)。

**文件分成「已確認行為」與「本次建議 API／回應格式」。**本次盤點不代表 OpenAPI、所有 HTTP code／欄位或新增功能已核定，也沒有實作 Runtime、修改共用資料 Schema 或 UI。決策由 [08 的 D-56／D-57／D-58／D-59／相關 Q-ID](08_implementation_plan.md) 追蹤。

## 1. 範圍與已確認基準

### 1.1 這份清單是哪一層

這裡盤點 **Retrieval Runtime 對外的業務 API**：Builder DEV 與自行部署到 FTEST／ENT 使用同一語意與實作，限制可配置已確認；先前建議放 E，但本輪依使用者指示暫緩管理者、存放位置與 Schema 的定案。Builder DEV 的可信路由先選定 System；獨立 Runtime 綁定既定 System。不把 system_id／tenant 任意覆寫放進業務 JSON。

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
- D-57：整批接收前預檢通過才入列、回 202；入列後逐文件結果，文件無 partial，Run 可 partial，無紀錄回 200＋unknown。這不是要求完成 Parsing／Embedding／Indexing 才回 202。
- D-57／D-58：首期需要 retire，已確認為直接刪除該 System／document_id 的儲存資料與搜尋索引，不是保留資料的邏輯停用；回應與執行方式仍待定。取消 queued／running 文件工作首期不做。
- D-58：一支 POST /v1/ingestions 接收非空 IngestionDocument[]，單筆也包 List；Parser 每次仍接收單份物件，不另開 :batch。
- D-58：新增文件存在性與全部 document_id 清單的查詢能力，資料來源為該 System 的實際儲存／索引，與 Runtime 工作狀態分開；清單需對 Chunk 的 document_id 去重。

## 2. API 清單：7 支業務 API＋2 支 Health API

**能力與 Ingestion List 格式已確認；存在／清單／retire 的具體路徑、完整 Envelope 與同步刪除建議仍為草案。**查詢以目標 System 為作用範圍，不直接開放任意 DB／Collection 管理。

| 優先 | Method／Path 草案 | 用途 | Request | 成功回應／狀態 | 主要行為 |
|---|---|---|---|---|---|
| P0 | POST /v1/ingestions | 提交一份或多份文件 | 非空 IngestionDocument[]，單筆也包 List | 202：run_id、queued、config_revision、文件清單；Location 指向查詢 | 整批預檢通過才入列；不再另開 :batch；每個 item 與 Parser input 同 Schema |
| P0 | GET /v1/ingestions/{run_id} | 查一次提交及逐文件結果 | run_id | 200：Run 狀態／計數／逐文件結果 | 資料來自 Runtime 記憶體工作紀錄；Run 可 partial |
| P0 | GET /v1/documents/{document_id}/ingestion-status | 查文件最近一次工作 | document_id | 200：run_id、status、Module、時間／錯誤；無紀錄為 unknown | 工作狀態，不用成功儲存的文件反推 |
| P0 能力；格式草案 | GET /v1/documents/{document_id}/exists | 查目前文件資料是否存在 | document_id | 200：document_id／exists | 從實際文件儲存／索引讀取；不是工作紀錄是否存在；backend 無法確認時回錯誤 |
| P0 能力；格式草案 | GET /v1/documents?limit=...&cursor=... | 列出目前全部 document_id | 分頁參數 | 200：document_ids／next_cursor | 去重且分頁讀完整清單；不是列 Chunk ID／工作紀錄 |
| P0 能力；格式草案 | POST /v1/documents/{document_id}:retire | 直接刪除文件資料 | document_id | 建議同步刪除完成回 204；精確行為待 API-D03 | 清除對應 Chunk／向量、持久儲存與本地搜尋副本，避免重啟重建復活；不取消 Ingestion 工作 |
| P0 | POST /v1/queries | 完整 Inference | {query, filters?, metadata?} | 200：根層 QueryContext[] | 同步完成；Runtime 控制 Rate／併發／Deadline |
| P0 支援 | GET /health/live | 程序存活 | — | 200：存活 | 不依是否有資料判斷 |
| P0 支援 | GET /health/ready | Runtime／必要資源初始化 | — | 200：就緒；否則 503 | 尚無可查索引不一律等於不 Ready |

共享 Builder DEV 的 System 選擇與資料權限由可信層決定，單一 Pod Health 不能代表每個 System 的 Query-ready。API-D06 涵蓋身分驗證、授權與路由；清單／存在／retire 也必須受相同存取邊界限制。

Document 管理細節見 §9。讀取整份文件／Chunk 內容、取消工作、單步 Module 測試仍不因加入 ID 清單而自動納入。

## 3. Ingestion 的提交與接收

### 3.1 已確認單一端點，單份也包 List

POST /v1/ingestions 的單份文件 body：

```json
[
  {
    "document_id": "manual-001",
    "source_revision": "v1",
    "content": {"text": "設備每月需清潔散熱孔。", "title": "保養規範"},
    "metadata": {"department": "manufacturing"}
  }
]
```

**API 每個 item＝Parser input**；不再把整個 HTTP body 與單份 Parser input 當成完全相同。共用 IngestionDocument 的欄位、content／base64／uri 三選一及驗證規則引用 [13](13_ingestion_parser_input_contract.md)／[Schema](../schemas/ingestion_document.schema.json)，沒有更改。HTTP List 由 Runtime 拆成逐文件工作，run_id 不放進 Parser 業務資料。

D-58 已確認根層 List。Runtime Request Schema／後續 OpenAPI 以 array＋items 引用共用 IngestionDocument，minItems=1；共用單筆資料 Schema 不改成 List。本輪尚未發布 Runtime OpenAPI／新增機器 Schema。

### 3.2 多份使用相同格式

```json
[
  {"document_id": "manual-001", "content": {"text": "設備每月需清潔散熱孔。"}},
  {"document_id": "manual-002", "content": {"text": "每週清潔濾網並記錄保養結果。"}}
]
```

根層 List 與物件包 List 都是實際 API 採用的方式：Meilisearch 的 Add or replace documents 使用根層陣列；Azure AI Search 的 Documents Index 使用 {value: [...]}。沒有必須分開單筆／Batch 端點的統一規定。

D-58 已確認一支 POST 固定接收非空 List，不同時接受 object／array 兩種 body。單筆也包 List；未來全批共用參數若有需求，再設計位置／版本。先前兩支端點與 documents wrapper 提案已取代，並非需要相容的已發布 API。

官方格式查核（2026-11-05）：[Meilisearch](https://www.meilisearch.com/docs/reference/api/documents/add-or-replace-documents)、[Azure AI Search](https://learn.microsoft.com/en-us/rest/api/searchservice/documents/?view=rest-searchservice-2025-09-01)。參考的是輸入形式，不照搬其持久化、部分接受或寫入語意。

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

提交一份或多份使用相同 receipt，一份只有一筆 documents；Receipt 的 documents 是回應格式，不代表 Request 必須有 documents wrapper。Receipt 是接受當下的快照，Client 查詢時可能已 running 或完成。

建議接收階段只做授權、JSON／外層 Schema、有效 Config／Parser 能力等快速預檢、文件忙碌檢查與容量預留。下載、昂貴 Parsing、Embedding／Indexing 在 Worker 執行，失敗由狀態 API 回報，不能把 202 當作最後成功。

**D-57 已確認：「預檢整批通過才入列；入列後逐文件獨立結果」。**例如外層不合法、同批重複 ID、某文件已 queued／running、容量不足時，先拒絕整次請求，保證沒有未交代的部分入列；接收政策與單一 List 包裝均已確認；完整錯誤／OpenAPI 規格另行整理。合法文件入列後，另一份文件 Parsing 失敗不回滾已成功文件。

併發與 Queue 容量建議以文件工作計數，並另限制排隊資料量／總請求大小，避免一個巨大 Batch 算一個 queue slot。具體數值、接收容量預留及公平排程見 API-D04。預留文件忙碌標記、Queue 容量與狀態紀錄須一致，不能檢查後因競態收進同文件兩份工作。

## 4. 文件狀態與一次提交的狀態

### 4.1 文件級狀態

**document_id 來自 Request 的每份 IngestionDocument，不需要先在索引中成功存在。**整批預檢通過、入列時即建立 Run 與每份文件的 queued 紀錄；Worker 更新 running，再記錄 completed／failed。失敗紀錄與成功紀錄同樣保留到終態清理，不只有成功文件才有狀態。

| 階段 | Runtime 工作紀錄 | 搜尋資料／判斷 |
|---|---|---|
| 入列前整批拒絕 | 不建立新的 Run／工作；HTTP 回位置與錯誤，可辨識時附 document_id | 不改既有文件；若有舊狀態，不覆寫成這次的新工作 |
| 已入列 | queued | 不代表已產生／寫入 Chunk |
| 執行中 | running，必要時附 Module | 舊版可仍存在，不能以此推算本次完成 |
| 執行失敗 | failed＋error | 工作失敗紀錄仍可查；不等於必有成功索引 |
| 成功發布 | completed | 才表示本次完整處理成功 |
| Runtime 重啟／紀錄到期 | 查詢為 unknown | 持久索引可能存在，不能據此假造本次工作狀態 |


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

D-57 已確認 Batch 彙總方向：仍有 running 為 running，只有等待且尚無終態為 queued；已處理部分且還有待處理文件時為 running；全成功為 completed、全失敗為 failed、已全部終結但有成功亦有失敗為 partial。**partial 只適用 Run 彙總，不適用半份文件發布。**沒有活躍工作但至少一筆結果未確認時，Run 為 unknown，不偽裝為全失敗或已確認 partial。Run partial／未知紀錄 HTTP 200 已確認；精確欄位與未知結果處理仍見 API-D02／05。

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

第一版採同步查詢，額滿直接拒絕或僅允許有上限的短等待；精確行為列 API-D04，不把查詢塞進 Ingestion 的長工作 Queue。實際 Rate／併發數需可配置；管理者、設定位置與格式依本輪指示暫緩定義，先前 E 是建議位置。不要把環境流量控制混入每次 query body 或搜尋演算法參數。

目前不需要另開 async Query／查詢工作狀態 API，也不增加獨立 Rewrite／Retrieval／Rerank 測試端點；後者需有明確需求再討論，既有 UIB-007／008 仍未核定。

## 6. HTTP、狀態與錯誤層次提案

| 情境 | 建議 HTTP／行為 |
|---|---|
| JSON 不可解析 | 400，未接受工作 |
| 授權缺失／不足 | 401／403，適用提交與所有狀態查詢 |
| Request body 超過限制 | 413，未接受工作 |
| 外層 Schema 不合法／同 Batch 重複 document_id | 422，附位置；整批預檢拒絕已確認，具體錯誤 code／位置格式待定 |
| 同 System 的 document_id 已 queued／running | 409，附目前 run_id 或可查狀態；不建立第二份工作 |
| System／使用者的請求速率或接收配額已滿 | 429，附可用的 Retry-After／錯誤原因；不回 202 |
| Runtime 不就緒／整體容量無法接收／Query 索引不就緒 | 503，使用可區別的 code；接收容量與 Query index-ready 分開 |
| 已成功接收 Ingestion | 202＋run_id／Location；尚未成功完成 |
| 202 之後的文件執行失敗 | 狀態 GET 仍為 200，文件 status=failed 與 error；不是將原 POST 改回 HTTP 500 |
| 狀態紀錄遺失／到期 | 狀態 GET 200＋unknown 已確認；不宣稱文件不存在，精確欄位列 API-D02 |
| Query 成功但無命中 | 200＋QueryContext[] 中的空候選 |
| Query 執行／上游 API 失敗或超時 | 依錯誤來源映射 5xx（502／503／504 等）與 code；不偽造成功結果 |

輸入預檢拒絕、工作執行失敗、索引可見性、狀態查不到是不同問題。錯誤碼與數值上限尚未完整核定，不能把這張表當成完整 OpenAPI。

202／狀態監看依據：[RFC 9110 §15.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)；429／Retry-After 依據：[RFC 6585 §4](https://www.rfc-editor.org/rfc/rfc6585.html#section-4)。RFC 支持 HTTP 語意，不替本專案決定 Queue 耐久性、批次政策或錯誤 Envelope。

## 7. 非必備端點與本輪待討論

### 7.1 首期不納入／後續能力

| 能力 | 狀態 | 後續界線 |
|---|---|---|
| 取消 queued／running 文件工作 | 已確認首期不做 | 未來另訂排隊移除、正在執行的中止／Remote 配合與已提交副作用；retire 不代替取消 |
| 整份文件／Chunk 內容查詢 | 先延後 | document_id 清單與存在查詢已納入；不因此提供內容、向量或任意 DB 查詢 |
| 索引詳細狀態／容量資訊 | 可作後續管理診斷 | index-ready／恢復／統計來源，不用 Health／最後 Run 反推 |
| Rewrite／Rerank 單步測試、async Inference／streaming | 目前不納入 | 有明確需求再定義，不重新引入 Generation |

Retire 已確認為直接刪除，不做 soft delete／restore API；再次使用同 document_id 需重新 Ingestion。同步／非同步、忙碌文件互斥、重複刪除、Remote 與快取一致性等細節見 §9／API-D03。

### 7.2 決策狀態與剩餘討論

| ID | 已確認 | 仍待確認／建議 | 關聯 |
|---|---|---|---|
| API-D01 | 單一 POST、非空 IngestionDocument[]、單筆也包 List；整批預檢通過才 202；逐文件結果 | 方向已收斂；完整 Runtime Request／錯誤 OpenAPI 後續整理，不改單筆共用資料契約 | Q-019／Q-009 |
| API-D02 | 保留 Run／文件兩種查詢；文件無 partial、Run 可 partial；無紀錄 GET 200＋unknown | 完整欄位／code、保留值、輪詢與回應上限；Remote 結果不明另見 D05 | Q-019／Q-017 |
| API-D03 | retire 直接刪除資料；不做工作取消或 soft delete／restore | 建議同步 204、無資料重複刪除也成功、忙碌文件 409；精確方式與後端／Remote 完整刪除能力待核定 | Q-008／Q-017／Q-028 |
| API-D04 | Queue／併發／Rate／Deadline／紀錄上限可設定 | 誰設定、存放處、Schema 與具體值暫緩；環境 E 為先前建議，不當作本輪已定 | Q-017／Q-020／Q-027 |
| API-D05 | Remote 結果不明回 unknown、不自動重試未知寫入；不做斷點續跑 | Config 以重啟／重建生效可避免熱切混用，但共享 Runtime 的影響範圍、Remote 在途操作及 Query 讀寫一致性仍需界定，見 §8 | Q-008～010／Q-015／Q-017／Q-028 |
| API-D06 | Builder 登入方式延後；Runtime API 先暫按 HTTP Basic Auth 規劃（由 basic oath 理解） | Basic 名詞若原意為 OAuth 需再對齊；HTTPS／帳密引用、身分作用域、Authorization／System 路由及 Health 暴露仍待細化 | Q-006／Q-019／Q-020 |
| API-D07 | 查 document_id 是否存在、列出當前全部 ID；讀取實際儲存而非工作表 | 建議 exists 布林值、ID 清單去重分頁；路徑／欄位、排序／cursor／分頁一致性、Remote 讀取能力待整理 | Q-019／Q-028 |

API-D01～07 沿用既有 Q-ID，不另凍結完整 OpenAPI。單一 List、接收／Run 彙總、取消暫緩、文件 ID 管理與 retire 直接刪除方向不再重問；存在／清單／刪除的精確格式與執行細節仍待核定。



驗收先採：單筆／Batch 接收、文件忙碌衝突、Queue 滿、逐文件 partial、狀態兩種查詢、重啟 unknown、同 ID 完整替換、Query 無命中／不就緒／限流，以及已授權 System 隔離。這些是未來實作驗收清單，不是本文件新增的可執行測試。


## 8. API-D05／06 的具體情境

### 8.1 Config 透過重啟生效，與共享 Runtime 的範圍

使用者提出 Config 更新時 Runtime 會重啟，因此不做執行中熱切。這符合 07 的獨立 Runtime 重部署方向：每個實例持有固定 Config，採用新 Config 時重新建立，舊的排隊／執行工作不轉移到新版繼續跑；程序重啟後狀態依既定政策為 unknown。

重啟可以排除同一個存活實例臨時改讀新 Config 的情境，但仍要區分：

- **獨立 Runtime**：可透過重啟／重新部署套用新 Config；持久 ES／MongoDB 索引仍需檢查 Profile／格式相容，重啟不等於已重新 Ingestion。
- **Builder 共用 Runtime**：同程序可承載多個 System；若改一個 System 就重啟整個程序，其餘 System 的 Queue／工作狀態與 Memory 索引也會受影響。建議重建目標 System 實例，或明確接受整個程序重啟的影響，具體流程仍待決。
- **Remote 在途操作**：Runtime 重啟不保證 External Service 已停止寫入，因此 §8.2 的未知結果／互斥問題仍存在。

初期不承諾熱更新／無損切換；是否等待活躍工作完成才重建、如何處理排隊工作與共享實例回收，需要與生命週期一起定義，不重新引入取消 API 或 checkpoint 恢復。

### 8.2 Remote 寫入可能成功但 Runtime timeout

例：Runtime 呼叫 Remote Indexing，服務已寫完或仍在寫，但回應超時。若當作沒寫入而立即重送，可能重複計算／寫入；舊操作若稍後完成，也可能覆蓋較新的提交。document_id 覆寫本身不保證解決所有時序問題。

D-59 已確認沿用 unknown＋可辨識原因，不自動重試未知寫入；如何確認結果、暫時限制同文件新提交、或要求服務提供冪等／版本控制，需與 Remote 協定一起定義。Runtime 重啟清空狀態也不代表 Remote 工作已停止。

### 8.3 同時進行 Ingestion 與 Query：鎖的最小範圍

例：舊文件 5 個 Chunk，新版 3 個。更新期間若搜尋與寫入交錯，可能讀到暫時的新舊混合。

**同文件寫入互斥**已確認：同一 (System, document_id) 不同時更新，retire 的忙碌互斥具體回應仍待核定。這與下列 **Query 的讀寫鎖**是兩件事。

最簡單的單程序方案是由 Runtime／Engine 維護同一 System 共用的鎖，Indexing 真正提交／retire 時持有，Retrieval 取得候選時使用同一把鎖；Parsing／Embedding 及後續 Rerank 不占這把鎖，避免整個模型呼叫期間阻擋查詢。這是設計示意，不凍結 Python SDK 的 lock 類型或介面。

此鎖只協調同 Runtime／同鎖管理範圍內的存取，不自動涵蓋其他程序、直連 ES 的客戶端或仍在執行的 External Service；ES refresh／資料可見性也需配合。不是資料庫交易或分散式原子發布保證。

使用者傾向 KISS、可討論接受極短更新窗口的競態。**是否省略 Query 讀寫鎖、接受暫時新舊混合，仍保留為取捨，未在本輪默默撤銷原有成功發布／失敗保留舊版要求。**若採此簡化，需明確記錄放寬的是更新期間的讀一致性；工作 completed 與刪除成功後仍須反映正確資料，不讓半份永久失敗結果冒充成功。不加入複雜分散式鎖／全索引快照作為本輪新需求。

### 8.4 Runtime API 暫定 Basic；Builder 登入延後

使用者要求 Builder 的使用者登入方式之後再討論；Retrieval API 暫訂 basic oath。本輪**先按 HTTP Basic Auth（帳號／密碼）理解並規劃，不視為 OAuth／Token 流程已選定**；若原意是 OAuth，需要再對齊名詞。這是暫定方向，不凍結企業帳號／權限模型。

HTTP Basic 以使用者名稱／密碼認證；部署採 HTTPS／TLS，帳密經環境 Secret 引用配置，不寫入文件資料或邏輯 Config。標準依據：[RFC 7617](https://www.rfc-editor.org/rfc/rfc7617.html)。

Basic 解決 Authentication（辨識呼叫者），不自動決定 Authorization（能否對某個 System 執行 Ingest、Query、查清單／狀態或 Retire）。共享 Runtime 的可信 System 路由、帳號作用範圍與 Health 暴露仍須界定；不能直接相信外部任意 Header 選租戶。

本輪不要求實作 Builder 登入／tSSO／SSO 管理流程，也不新增 OAuth 服務。Basic 的具體檢查位置、帳密管理與 Gateway 整合依部署條件後續討論。

## 9. 文件資料查詢與直接刪除

### 9.1 資料來源與工作狀態不同

這裡的 DB 是該 System 綁定的文件資料／索引後端，可能是 Elasticsearch、Local Memory、MongoDB 配本地搜尋或支援協定的 Remote Service；不要求為了查 ID 新增一個中央 DB。查詢以目前有效／已發布的文件資料為準，不把尚未發布的 staging Chunk 當成成功文件。

預設儲存單位是 Chunk，透過其 document_id 判斷存在與去重列出文件，不要求額外長期保存 ParsedDocument。實際後端可用適當 metadata／catalog 加速，但必須與資料一致，不能以 Runtime 的工作紀錄當成唯一依據。API-D07 保留實體布局與查詢策略的實作選擇。

| 問題 | 查詢位置 | Runtime 重啟後 |
|---|---|---|
| 最近一次 Ingestion 是否成功／失敗 | Runtime 記憶體工作紀錄 | 無紀錄為 unknown |
| 文件目前是否存在／有哪些 ID | System 實際文件儲存／索引 | ES／MongoDB 等持久資料仍可在後端就緒後查；Local Memory 資料若已遺失則清單為空 |
| retire 是否刪掉文件資料 | 直接刪除對應儲存、索引與本地搜尋副本 | 不能只清記憶體索引而保留供重建資料，否則可能重啟復活 |

「更新失敗但舊版仍存在」可以同時得到 ingestion-status=failed、exists=true；「成功後已 retire」也可以同時是歷史工作 completed、exists=false。這些不是矛盾，不把狀態改成 retired 或抹掉成功紀錄來代替資料查詢。工作歷史仍按其記憶體保留政策清理。

### 9.2 存在查詢提案

GET /v1/documents/manual-001/exists

```json
{"document_id": "manual-001", "exists": true}
```

不存在時建議仍為 200 並回 exists=false。後端無法連線、尚未初始化或不支援操作時，應回可辨識錯誤，不回 false 偽裝不存在。這支 API 不回原始內容／Chunk／向量，也不表示最近一次工作成功。

### 9.3 ID 清單提案

GET /v1/documents?limit=100&cursor=...

```json
{"document_ids": ["manual-001", "manual-002"], "next_cursor": null}
```

完整清單直接查該 System 的實際 ES／Local 資料，對 document_id 去重並分頁；一份文件有多個 Chunk 仍只回一個 ID，不無限制一次塞入全部結果。limit=100 僅是例子，不是已核定預設值；頁面排序、cursor 有效期與同時寫入時的一致性見 API-D07。初版不要求計算全量 total 或提供內容投影。

後端實作可依布局選擇：ES 以可精確聚合的 document_id 欄位作去重，候選是 composite aggregation，使用回傳 after_key 接續頁面；不能只取前 N 個 Chunk hits 去重，就當作已列出所有文件。Local 可由 Chunk store 的 document_id 去重集合或一致維護的文件對照取得，MongoDB 模式使用實際保存的文件資料；不查 Runtime 工作表，也不需要為這個 API 再建中央目錄 DB。

ES 分頁聚合依據：[Composite aggregation](https://www.elastic.co/docs/reference/aggregations/search-aggregations-bucket-composite-aggregation)。具體 Mapping、排序、資料更新中的頁面一致性與效能仍由 Artifact／backend 驗證，不把方案寫成已實作。

### 9.4 Retire 直接刪除

Retire 刪除該 System／document_id 對應的 Chunk、vectors、全文／向量索引，以及供恢復／重建使用的持久儲存與搜尋副本。具體儲存布局由 Artifact／backend 決定，不因 ID 命名相同就刪除其他 System 的文件，也不要求刪除使用者傳入 URI 所指的外部來源檔案。

本輪建議同步完成後回 204；相同文件已不存在時視為已達刪除目標，重複呼叫仍成功；同文件仍 queued／running 時建議 409，先不取消工作。這些 HTTP／互斥細節仍待 API-D03 核定。後端 timeout 或部分刪除未確認時不能回完整成功，後續查詢／重試及清理需與後端政策對齊。

刪除成功後文件不得再被 Query 返回，exists 為 false，ID 清單也不再列出。此處沒有 soft delete 標記或 restore；若需要再次使用，重新提交文件 Ingestion。Retire 不透過改寫 metadata／Query filters 來假裝完成實際刪除。

### 9.5 Local／Remote 的能力配套

Document 管理是索引／儲存管理能力，不新增 Pipeline Module。平台可直接管理後端時由對應 storage／index adapter 提供操作；私有 Remote Service 管理資料時，需有配套的存在查詢、ID 列表與刪除 operation／受控存取方式。只提供 Parser／Embedding／Rerank 的無狀態服務不因此被要求支援文件管理。

Descriptor／Manifest／Artifact 配套須能描述支援方式；具體欄位及 SDK／Remote operation 介面仍待定，不新增 IndexBinding 根鍵。服務不支援時要明確回報／卡控，不回空清單、exists=false 或成功 retire 假裝有能力；Query／已註冊與文件管理可用性也需分開驗證。
