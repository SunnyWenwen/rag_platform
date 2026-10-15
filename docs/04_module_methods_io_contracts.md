# RAG Engine — 組裝、執行與模組開發規格

> 文件集 v0.16 · 2026-10-15 · 開發規格草案
>
> 本文涵蓋可獨立執行的 Engine 與各模組；正式名詞定義見 [03 §3](../03_architecture_proposal.md#terminology)，共用資料／Config 結構見 05。既有產品語意為已確認方向，新增 SDK、Registry 形狀、執行政策為建議，須經對應 Q-ID 核定。本次未新增 Engine 程式。

## 1. 目標與依賴邊界

**開發者提供 Config 及必要服務，即可直接執行 Ingestion／Inference；不需要 Builder UI、Builder DB 或 HTTP。**Engine 負責模組組裝，07 只呼叫此能力並包裝 API／工作狀態。

Ingestion：Import → Parsing → Chunking → Embedding → Indexing。
Inference 基線：Query Transformation → Retrieval／Fusion → Rerank → Generation。目標需可設定融合策略與合併時點；Engine 依核定 Fusion Plan 保留逐路結果與組合 Fusion／Rerank，見 §5.2。
Evaluation：重用相同檢索／問答入口的評估邏輯，任務排程與報告儲存由 07 負責。

- 固定 Pipeline，不要求使用者建 DAG。
- Config、業務 Payload、可信 RunContext 分開；資料結構見 [05](05_data_contracts_search_design.md)。
- LangChain 物件只在 Adapter 內轉換，不作持久化／跨模組 Contract。
- 不同框架／自訂 Function 或 Class 透過相同 Contract 包裝。
- 純全文可跳過 Embedding；None 模組回傳相同語意的 pass-through 結果。

## 2. Engine 入口與初始化（建議，Q-002／Q-017）

### 2.1 Python 介面草案

```python
# 目標用法示意；目前尚未存在這些類別，命名待 Q-002 核定。
config = load_config("rag.yaml")
engine = RAGEngine.from_config(
    config,
    service_resolver=services,
    state_store=stores,
    registry=registry,
)
await engine.start()
try:
    result = await engine.ingest(ingestion_input, context=trusted_context)
    answer = await engine.query(query_input, context=trusted_context)
finally:
    await engine.aclose()
```

服務解析與 Store 使用可替換接口；Memory 模式不要求遠端 DB。Config 是模組／Pipeline 邏輯，service_resolver／Store／Binding 由部署設定解析；同一 Config 可套用不同環境綁定而保持處理語意一致。start／query 的非同步選擇、生命週期、公開回應型別、Evaluation Target 介面須核定。直接 SDK 可建立 System，不回 HTTP code；07 將領域錯誤映射為 HTTP／Job 回應。

### 2.2 編譯與初始化流程

1. 讀取 YAML／JSON，驗證 Contract 版本及未知欄位；安全解析，不執行設定內的程式碼。
2. 將 UI Draft 編譯成 Effective Config，排除未啟用方法／服務草稿。
3. 根據 Registry 驗證 I/O、方法能力、欄位來源、Profile、模板與可過濾能力。
4. 依部署設定解析 Config 中的服務邏輯引用與 Secret；以受授權的 Workspace／System／集合建立 Binding，不把環境 URL 或目標集合混成模組邏輯。
5. 初始化被使用的 Client／Tokenizer／Parser／Index Adapter；不載入未使用服務。
6. 若有既存資料／Manifest，檢查相容性；MongoDB 模式按相容版本重建 Local Search。
7. 回報初始化結果及索引就緒狀態；失敗釋放已開啟資源，不留下半個可查詢實例。

Schema 格式檢查、真實連線檢查、Profile 相容檢查、索引可查詢是不同狀態。Runtime 可啟動且接受 Ingestion，不代表 Query 已可用。

### 2.3 Registry／Factory

建議每個註冊方法提供 module_type、module_id、implementation_version、input_schema、output_schema、config_schema、requires、provides、supports 及 factory。由 Engine 編譯器串接，不由 Builder 寫另一套組裝流程。

```yaml
module_id: company.chunking.recursive
module_type: chunking
implementation_version: 1.0.0
contract_version: 0.1-draft
requires: [document.string_field, tokenizer]
provides: [chunk.fields, chunk.locations]
supports: {async: true, batch: true, streaming: false}
```

宣告能力須有契約測試。套件／版本、entry point 解析與依賴鎖定見 Q-001／Q-022；不直接 import 任意使用者輸入的 Python 路徑。

## 3. 共用執行政策

### 3.1 I/O 接線

每步邏輯形式為 `Module.run(input, context) -> ModuleResult[T]`。實作前確認 async／batch 能力；取 result.data 作下游 Payload，不把 metrics/errors 當業務資料。

| 模組 | 業務 Input | 業務 Output | 另行注入／保留 |
|---|---|---|---|
| Import | files／標準 records | SourceAsset 清單 | 來源授權、資產保存 |
| Parsing | SourceAsset 清單 | ParsedDocument 清單 | Schema、Parser routes |
| Chunking | ParsedDocument 清單 | Chunk 清單，vectors={} | Tokenizer、必須繼承資訊 |
| Embedding | Chunk 清單 | 相同成功 Chunk＋vectors | Profile、逐項錯誤；不回獨立 VectorSet |
| Indexing | 帶向量或純文字的 Chunk 清單 | IndexBinding、逐項結果、可搜尋狀態 | 授權目標／刪除事件；提交政策待決 |
| Query Transformation | 原始問題 | 原始問題＋SearchQuery 清單 | llm_ref、Prompt |
| Retrieval | 原始問題、SearchQuery 清單、IndexBinding、filters | 基線為原始問題＋SearchHit 清單；可配置 Fusion Plan 需保留逐路候選，形狀待 Q-002／Q-014 | Query Encoding、可信授權範圍、query／route identity |
| Rerank | 原始問題、SearchHit 清單 | 原始問題＋重排後 SearchHit 清單、applied | 模型服務與內容欄位 |
| Generation | 原始問題、SearchHit 清單 | QueryResult | 共用 LLM、Context Budget |
| Evaluation | Dataset、Target | 逐題結果與指標摘要 | 版本綁定、Judge；工作儲存由 07 提供 |

原始問題不被 Rewrite 覆蓋。新版不預設公開對話歷史；歷史若啟用需另訂契約，不因舊草案有 history 欄位就宣告已支援。

原始問題是 Inference 的持續傳遞資料：Query Transformation → Retrieval／Fusion → Rerank（含 None）→ Generation 都必須保留，不能只在第一步或 HTTP 層暫存後丟失。`include_original` 只控制是否把原始問題加入搜尋 Query 清單，不影響 Rerank／Generation 仍取得原始問題。逐 Query 的 Rerank 若改用衍生 Query，需依 Q-014 的計畫顯式定義。

### 3.2 錯誤、重試與觀測

- 結果必須能對應輸入的成功／失敗／skipped 項目。空檢索為成功，索引或 Provider 故障為失敗。
- `partial` 的提交方式未定前，不能自行接受半文件索引並刪舊文件。
- 重試由共用政策管理；HTTP 重送與內部重試不能形成無界倍增。僅在可安全重試且暫時性錯誤時啟用。
- Indexing／資產提交具副作用，需冪等與版本檢查。讀取 checkpoint 不等於提交 checkpoint。
- 每個模組記錄 System／Config／Run／Trace、耗時、數量及標準錯誤；不記錄真實 Secret。未知用量不填 0。
- Provider failure 不偽裝成沒有相關資料；fallback 需明示 warnings 及實際方法。

Timeout、重試預算、取消、partial 與 fallback 尚待 Q-009／Q-017／Q-023 定案；開發可先以明確錯誤與不自動重試完成骨架。

## 4. Ingestion 模組

### 4.1 Import

**目的與邊界**：接收、驗證、建立來源資產；不做 PDF／OCR 或 Embedding。files 與 records 是同一流程的不同入口，不要求 System 二選一。

**Config／I/O**：依 05 的 accepted_inputs、CSV mapping 與 SourceAsset 草案；HTTP 大小限制由 07 執行，直接 SDK 也需同等限制。

**處理**：

1. 驗證來源可讀取、格式／大小與可信身分；檔案 MIME／內容偵測策略待定。
2. JSON records 依 input 來源欄位檢查；Builder CSV 已映射為相同格式，不在 Parsing 重映射。
3. 產生資產關聯；保持明確文件 ID／來源版本；檔案派生多文件由 Parser 合作處理。
4. 提交可供下游讀取的資料；原始檔保留與暫存刪除需 Q-016。

**例外**：空批、同批重複 ID、來源不存在、型別不符、超限、無權讀取。空批允許 no-op 或拒絕、資料重送見 Q-008，不用 Prototype 行為代替正式決策。

**驗收**：CSV 轉標準 records 與直接 records 得到相同 ParsedDocument；來源／ID／保留資訊不遺失；未授權 URI 被拒絕。

**待決**：Q-005、Q-007、Q-008、Q-016、Q-019。

### 4.2 Parsing

**目的與邊界**：依格式擷取內容，輸出五個 key 的 ParsedDocument。Parsing 不生成向量、不自動摘要。

**方法**：Structured records、Native text、PDF／PPTX 擷取及 OCR 路由。首批實際支援格式／套件未定，不能因 UI 顯示選項就宣告支援。

**處理**：

1. 以格式路由至已註冊 Parser；同格式策略明確選定。
2. 擷取文字／表格／章節，按 Schema 寫入 fields，位置寫 structure。
3. 結構化 records 已使用目標欄位，僅整理及驗證；不做第二次 column mapping。
4. 多文件來源派生穩定 ID，保留資產關聯；驗證完整 Schema。
5. 沒有結構時 structure={}，不能捏造 headings 或頁碼。

不同格式的 Parser routes 可在同一 System 同時啟用，依每筆來源格式分派；同一格式選一個有效策略，例如 PDF 使用原生擷取或核定的 OCR／fallback 策略。實際平行度受資源與執行政策控制，不要求使用者把不同格式拆成不同 System。

**例外**：掃描文件未啟用 OCR 回 `OCR_REQUIRED` 或等價領域錯誤；零文字不能當作可檢索成功。損壞／加密檔案、讀取順序、空白頁及表格策略見 Q-005。

**驗收**：直接文字與掃描檔可辨別；Unicode offset／頁碼可對回內容；一檔多文件不共用同一 ID；未支援格式有明確錯誤。

**待決**：Q-005、Q-006、Q-007；新格式能力需同步 Registry／UI。

### 4.3 Chunking

**目的與方法**：Recursive／Header-aware；一個主要 split_field＋多個 copy_fields／metadata_fields。以 Token 計量，不新增字元模式。

**處理**：

1. 檢查主要欄位為非空必填 string、copy 欄位可取得。
2. Recursive 依 separators 優先序切分，必要時處理過長片段；size 是上限、overlap 是目標值。
3. Header-aware 先依可靠標題層級切分，再對超長章節 Recursive；缺 headings 不能假裝成功。
4. 計算原 fields 字串範圍及跨 block／page locations，不從帶 overlap 的文字猜測位置。
5. 複製指定欄位；文件摘要保持文件摘要；必需來源／ACL 不可取消。
6. 依有效切分設定及位置產生 chunk_id，初始化 vectors={}。

**驗證／例外**：size／overlap、Tokenizer、重複文字與非 BMP 字元、空段、極長無分隔文字。複製欄位未被主要內容切分，不保證其長度小於 size。

**驗收**：單塊不超過約定 Token 上限；offset 可精確還原主要文字；相同輸入與切分設定得到相同 ID；標題能力不足會拒絕。

**待決**：Q-004、Q-005、Q-007；Token 精確計數、切分 fallback 與 overlap 邊界需測試材料。

### 4.4 Embedding

**目的**：選 fields 內容，依 mappings 將 Dense 向量寫入 vectors。多個 output_name 與來源明確對應；與 Indexing 分離。

**處理**：

1. 解析 Profile／服務／Tokenizer，依 document encoding 建立每筆輸入。
2. 對實際來源內容檢查 Token 極限，含前綴及特殊 Token；不能只驗 Chunk Size。
3. 按 Batch Size 呼叫 Embedding Adapter；現有 Prototype 的格式基線為 OpenAI-compatible embeddings。正式首組服務、相容範圍及模型契約仍待 Q-003，不把原型格式當作所有 Embedding API 的通用標準。
4. 驗證回應 index 對應、數量、維度與有限值；不能因回傳順序錯誤把向量寫給其他 Chunk。
5. normalization 與 metric 依 Profile 執行；記錄模型／版本／Provider request ID。
6. 寫回原 Chunk.vectors；保留 fields／metadata。純全文 Pipeline 不初始化此服務。

**例外**：缺欄位、超長、429／Timeout、批次缺項、維度錯誤與非法數值。截斷或 partial 需明確政策，不能默默處理。

**驗收**：一筆 Chunk 可有兩個具名向量；後續仍取得原文；Query Encoding 依相同 Profile 配對；換模型／維度被判需重建。

**待決**：Q-003、Q-004、Q-009、Q-017。Sparse、多模態及 late interaction 為後續。

### 4.5 Indexing 與搜尋 Adapter

**目的**：保存 Chunk，依欄位用途建索引，回報寫入與可搜尋狀態。Engine 在初始化時透過 Adapter 準備授權範圍內的目標；不依賴 Builder 才能 provision。

**處理**：

1. 檢查 stored／fulltext／vector／filter 欄位與 Profile；ID／版本／來源／ACL 固定保留。
2. 比較目標 Schema／Profile，拒絕不相容寫入，避免不同模型混在同一向量欄位。
3. 依版本／冪等策略寫入 Chunk，維護 chunk_id 對照及 Binding。
4. 按後端 refresh／發布規則回報 searchable；write_acknowledged 不等於 searchable。
5. 更新／刪除與舊版本清除依 Q-008／Q-009；尚未核定不能自行宣告文件原子替換。

| Adapter | 內部責任 |
|---|---|
| ES | 組合 Mapping；全文 text、精確 keyword、Dense vector；保存投影；相容查詢及 refresh |
| Local Search | 每個具名向量管理 FAISS index；每個全文欄位管理 BM25；向量 ID → chunk_id；完整 Chunk 共用一份 |
| Local／MongoDB | 保存 Chunk／vectors／Profile Manifest；重啟按相容版本重建搜尋結構，不重新 Parsing／Embedding |

FAISS 的維度／metric 不足以證明向量空間相容。cosine／inner product／L2 的 normalization 與對外 relevance 轉換必須定義；中文 BM25 需斷詞方案。不能把 post-filter 與 Top-K 前授權過濾視為等價。

**驗收**：ES 與 Local 共用契約測試；完整內容可取回；不出現跨 System Chunk；寫入失敗／不就緒不回可查詢；Memory 重啟清空、MongoDB 可驗證恢復。

**待決**：Q-008～Q-013、Q-015；ES 版本／授權 Q-001。

## 5. Inference 模組

### 5.1 Query Transformation

**方法**：None／Rewrite／Multi-query；原始問題永遠保留。count 指衍生 Query 數，不含選配原始問題。

**處理**：None 回一筆原始 Query；Rewrite 使用 {{query}} 產生一筆；Multi-query 使用 {{query}}／{{count}} 產生多筆。include_original 由程式處理，不交由 Prompt 決定。引用 System 共用 llm_ref。

**驗證**：非空問題、合法模板、LLM 引用、衍生結果數量／文字合法。去除相同問題、模型輸出格式不符及降級政策由 Q-003／Q-023 核定；不自動忽略壞結果。

**驗收**：Rewrite 不覆蓋 original_question；Multi-query count 與原始問題選項獨立；None 不呼叫 LLM；Rerank／Generation 始終取得原始問題。

### 5.2 Retrieval

**目的**：選已索引的全文／向量欄位，自動推導 Dense／全文／Hybrid；後端由 Binding 繼承。

**處理**：

1. 取得對應 Config／Binding，確認 Profile 與資料就緒。
2. 將預設 filters、本次 filters、可信 ACL 以 AND 合併，驗證欄位／operator／值。
3. 建立每個 Query × 全文／向量欄位的路徑；向量路徑依其 Profile 使用 query encoding。
4. 每路在合法候選範圍內取 per_route_k，保留實際回傳的 rank、分數、方向與命中 Query。若 Adapter 在 ES 內部完成融合，接收已融合的一份清單並記錄計分設定；不要求憑空還原未回傳的分項清單／排名。
5. 轉換距離為越大越相關的 relevance；保留 query／route identity，依核定計畫及 chunk_id 對齊融合。
6. 在計畫指定的最終合併點後才取最終 top_k；既有單層基線在 Rerank 前完成。若計畫在逐 Query Rerank 後才跨 Query 融合，不能提前攤平或套用全域截斷；各階段 K／N 由 Q-014 定義。
7. 在 Rerank／Generation 使用候選前批次取回所需 fields／metadata，保留各路排序與身分；vectors 可省為 {}，下游無須知道 MongoDB 或 FAISS。

**需求與基線要分開**：使用者在 2026-10-14 明確追問「在哪一步合併」，因此必須能表達融合策略及合併時點。v0.8 Prototype 的所有 Query × 欄位單層融合、Rerank 前執行只是歷史基線。v0.9 已提供 [10](10_ui_adjustment_backlog.md) 的兩層時點 UI 與有效計畫推導；未實作真正的搜尋／融合。單一路是否略過融合仍依有效計畫判斷，文件分組不以清單數量為必要條件。

已確認的 UI 範圍：同一 Query 多路合併、跨 Query 合併，各自可在 Retrieval 後或 Reranker 後執行；兩者新建預設勾選且在 Retrieval 後。先逐 Query Sum Score、再跨 Query RRF 是可表達情境。具體 stage 枚舉、分數方法、正式配置 Schema 與 Adapter 支援仍由 Q-014 核定，原型展示初值不等同新增產品決策。

Engine 必須在計畫需要時保留 query_id／route_id、各路候選／分數／rank，不能先攤平成唯一 SearchHit 清單而丟失後續跨 Query 融合所需資訊。規格核定前可交付現有單層基線，但不得宣稱合併時點選擇已完成。

2026-10-15 使用者進一步確認可自行決定在哪個合法步驟後融合，並要求先討論 Inference 的資料／評分紀錄。以 [05 §4.6](05_data_contracts_search_design.md#inference-state-draft) 的 InferenceState／QueryContext／ResultSet 草案作為下一輪討論起點；具體型別未定案，不把說明用 Plan A／B 寫成唯一可用的固定流程。

- Sum Score（現有單層基線預設）：`sum(weight × relevance_score)`；未命中該路為 0；同類型欄位及各 Query 共用全文／向量權重；不自動正規化。
- RRF：`sum(1 / (k + rank))`；各路 rank 從 1；預設 k=60。

原始 BM25／向量分數尺度可能不同；現有單層基線採 Sum Score，不等於等權就有相同實際影響，也不預先決定新 Fusion Plan 的預設。距離轉換、同分順序、各路候選截斷的評估仍需 Q-011／Q-014。

同文件片段分組不是 chunk_id 去重。max_chunks_per_document 仍待定。融合計畫的具體規格追蹤 Q-014：若先逐 Query Rerank 再跨 Query 融合，需定義 Rerank 的問題、每路 Top-N、跨路相同 Chunk 與分數比較，不能只搬動一條流程箭頭；Rerank=None 時也不能無聲丟掉必要融合。

**驗收**：同 Chunk 多路命中按計畫去重；少於 K 或零筆為合法；多路套用相同授權；融合可人工驗算；無效 filter 拒絕而不變無條件搜尋。合併時點核定後，另驗證逐 Query／跨 Query 與 Rerank 次序、各階段截斷及 Trace；不能只有策略下拉選單而沒有實際路徑變化。

<a id="result-processing"></a>

### 5.2.1 ResultSet 後處理與共同排序

2026-10-15 14:24～14:31（Asia/Taipei）確認後處理收斂為三類：

| 操作 | 輸入／行為 | 輸出 |
|---|---|---|
| 去重＆合併 | 對選入清單依 group_by 分組、merge_key 對齊，再依方法計分 | 每個處理群組的新清單；Sum Score／RRF 為合併方法，不是額外一類操作 |
| 取 Top N | 對已排序的每份選入清單保留前 N 筆 | 分數／方向保留，候選不足時回傳可用數量 |
| 新模型算分 | 依明確 Query、服務與內容欄位評分 | 新分數及來源對應；具體缺項／服務限制仍待 Q-003 |

三者共用排序與 rank 更新，對外 ResultSet 永遠有序，rank 為從 1 起的連續整數；不輸出 rank=None。Top N 的輸入已排序，截取後仍符合此契約。共用排序按 score_order，平手規則仍待 Q-011／Q-014。每次建立新 ResultSet，保留選入來源；歷史結果不自動再參與，None 原樣傳遞 active 結果。

ResultSet 是資料；下一步由邏輯 Config 的核定計畫驅動。operation 記錄已執行的方法而非下一步指令，source 可供來源策略與追溯，score_kind／score_order 提供分數語意。正式 DTO 與範例見 [05 §4.6](05_data_contracts_search_design.md#inference-state-draft)。使用者要求的是可配置合法位置，不只固定 A／B 流程；[09](09_inference_contract_ui_plan.md) 提供尚待討論的順序式 UI 與來源選取方案。

### 5.3 Rerank

**方法**：None／DEV test use／Rerank API。服務端第一版平台約定：

```json
{"model":"reranker-a","query":"原始問題","documents":["候選 A","候選 B"],"top_n":2}
```

```json
{"results":[{"index":1,"score":0.92},{"index":0,"score":0.61}]}
```

這是平台契約，不是所有模型服務的通用標準。POST 路徑為選定 Base URL 下的 /rerank；其他格式需 Adapter。

**處理（既有 API／原型基線，目標遷移見下段）**：按 content_fields 順序把每筆候選組成文字；保持候選 index 對照；驗證 index 唯一且在範圍內、score 有限；映回原 SearchHit。輸出只能是候選子集，不改文件／ACL。None 原樣傳遞且不使用 Top-N；實際候選少於 top_n 時取可用數量；零筆不呼叫服務。

**驗收**：不生成新 chunk_id；重新 rank；保留原 Retrieval Trace。串接 Timeout／錯誤時不假裝 Rerank=None。

**與最新結果操作的對齊**：Rerank 是「新模型算分」的一種方法；模型輸出經共用排序、Top N 及 rank 更新。Top N 保留為可獨立描述的操作能力，但最新 UI 不要求獨立卡片，而是動作的收尾參數；v0.9 的 Reranker 輸出 Top N 預設 3，見 [10](10_ui_adjustment_backlog.md)。原型 API 說明要求 top_n 等於輸入 documents 數、回應完整評分，再由平台依 UI 上限截斷；正式 Adapter 的完整覆蓋驗證與服務上限仍待 Q-003／Q-014，不能默默依服務預設值少回候選。

**待決**：Q-003、Q-014、Q-017、Q-023；內容欄位分隔、輸入極限、全候選評分與服務回傳缺項政策需核定。

### 5.4 Generation

**方法**：由 llm_ref 取共用 LLM，沿用已確認的 DEV test use／OpenAI-compatible API 服務方向；現有 Prototype 以 Chat Completions 為格式基線，正式首組服務相容範圍見 Q-003。Context Assembly 在本模組內，不增加 UI 模組。

**處理**：

1. 依候選排序、內容欄位及 Token Budget 決定實際送出的 Chunk。
2. 逐筆套用 chunk_template，例如 `[{{citation_id}}] {{fields.title}}\n{{fields.text}}`。
3. 合併成 {{context}}，再代入回答 Prompt 的 {{query}}／{{context}}；query 是原始問題。
4. 只做一次變數替換，不執行程式或遞迴解讀文件內的 {{...}}。
5. 計算整體輸入與輸出預留，呼叫 LLM，驗證引用對應並產出 QueryResult。

Budget 必須計入 Prompt、問題、模板、Context、特殊 Token 與輸出預留。Context Budget 不是模型總長度。used_chunk_ids 表示實際送入內容，不保證模型每項主張都獲支持。

**例外／待決**：空 Context 的建議行為為 abstain；Context 截斷、過大單塊、未知引用、模型拒答／Timeout、Prompt 角色、Temperature 限制與 Citation 擷取見 Q-003／Q-023。不能把建議 abstain 當成已核可的所有場景政策。

**驗收**：引用只指向實際 Context；超限不默默丟資料；正確處理缺 title 等選填欄位；原文中的模板符號不再執行；不以固定答案通過整合驗收。

## 6. Evaluation 邏輯

獨立 Engine 測試可直接對本機 Engine Target 執行；Builder Runner 也可透過 Runtime Client Target 呼叫相同功能。**評分邏輯在本層，工作排程、狀態與報告保存由 07 管理**。檢索專用 Target 是否提供公開 API 由 Q-018／Q-019 核定，不能重寫一套不一致的 Retrieval。

建議 QARecord：case_id、question、expected_answer?、relevant_document_ids?、relevant_chunk_ids?、metadata_filter?。DatasetRef／Target 綁定 System、Config、資料版本、Engine／模型／Judge Profile。

| 指標 | 必要輸入 | 要定義的語意 |
|---|---|---|
| Recall@K／MRR | relevant IDs、實際候選與排序 | Chunk／Document 層級、Rerank 前或後、K |
| Answer Correctness | 問題、答案、參考答案及 Rubric | Judge／Rubric 版本 |
| Faithfulness | 答案、實際 Generation Context | 是否受資料支持，不等於世界真實性 |
| Latency／Usage／Error Rate | 各題 Trace／結果 | 失敗題不能任意排除 |

缺 Ground Truth 的指標應拒絕或明示 skipped，不能填 0 假裝已評分。relevant IDs 缺失與空清單不同；Chunking 改變後舊 chunk-level 標註不可直接沿用。詳細首批指標、Dataset Schema、Gate、Target API 與 Judge 見 Q-018。

## 7. 客製化與擴充

優先考慮 Chunking、Query Transformation、Rerank、Evaluation 的自訂邏輯。Import／Parsing／Embedding／Indexing／Retrieval 以註冊 Adapter 擴充；Generation 先以 Prompt／內容設定處理。

共用邊界：Config 驗證 → Input Validation → 執行政策 → 自訂邏輯 → Output Validation → 來源／ACL／語意檢查。Pydantic 不取代「Rerank 只能選候選子集」等語意驗證。

安全執行、套件 allowlist、Image 建置與版本鎖定未定前，不允許在共享 Runtime 對任意使用者程式 exec。是否第一期僅支援開發者註冊、是否有 UI 上傳與隔離試跑見 Q-022。

## 8. 待討論與決策

| 範圍 | 問題 |
|---|---|
| Engine SDK／Config／版本 | [Q-001](08_implementation_plan.md#q-001)、[Q-002](08_implementation_plan.md#q-002) |
| 模型、Token、Parser | [Q-003](08_implementation_plan.md#q-003)、[Q-004](08_implementation_plan.md#q-004)、[Q-005](08_implementation_plan.md#q-005) |
| ID、更新、提交與查詢一致性 | [Q-007](08_implementation_plan.md#q-007)～Q-010 |
| BM25／FAISS、MongoDB、filter、fusion | [Q-011](08_implementation_plan.md#q-011)～Q-014 |
| 重試、評估、客製化、Fallback | [Q-017](08_implementation_plan.md#q-017)、[Q-018](08_implementation_plan.md#q-018)、[Q-022](08_implementation_plan.md#q-022)、[Q-023](08_implementation_plan.md#q-023) |

## 9. Engine 完成條件

- 不啟動 Builder／HTTP，就能用完整 Config 跑真實 ingest／query。
- Config、Registry 與下游欄位相依可驗證；缺服務／能力得到可定位錯誤。
- Local Memory／MongoDB／ES 的差異被 Adapter 封裝；同一對外 Contract 不依賴框架內部物件。
- 固定測試可驗算 Chunk／offset／fusion／Filter／Citation；真實模型／搜尋另有 integration 證據。
- 尚未核定能力回報不支援，不以 Mock 或靜默 fallback 代表完成。

開發階段與驗收資料見 [08](08_implementation_plan.md)。
