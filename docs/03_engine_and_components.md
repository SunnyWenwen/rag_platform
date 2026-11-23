# Engine 與模組

Engine 用固定的 Ingestion／Inference 骨架編譯有效設定。每次執行使用同一 Config Revision，解析相依資源、驗證邊界、執行方法並記錄狀態。Builder、AI 助手與獨立 Runtime 共用設定驗證。平台內部 Registry／Factory 管理已交付的內建方法與 Remote Adapter。

Engine 以 LangGraph 執行共用的 Ingestion／Inference 流程，各 System 傳入該次執行固定的設定快照。Component 接收當次輸入、參數與資源依賴。System 的載入、索引綁定與工作狀態由 [Runtime 管理](06_runtime_api_and_deployment.md#src-07-4-systemrevision-與-engine-生命週期)。

<a id="remote-api"></a>
## User 接入 Remote API

User 提供已部署的 HTTP 服務，在選用 Remote 的節點設定服務網址、認證、服務版本、連續範圍及參數，欄位見 [Remote 節點設定](05_system_config.md#remote-node-settings)。Builder 依上游產生 Request Schema，依宣告與共用契約產生 Response Schema。Runtime 啟動時從 System Variable 解析 `connection.url`，以 POST 呼叫該網址，套用節點的逾時及自訂 Header。共用封裝由 [Remote API Schema](../schemas/remote_api.schema.json) 定義，服務開發者可直接使用 [OpenAPI](../examples/user_remote_api/openapi.json) 和 [驗證範例](../examples/user_remote_api/README.md)。

| 邊界 | 執行規則 |
|---|---|
| 請求 | Runtime 依 Remote 節點填入 `contract_version`，並以 `segment.module`、`segment.through` 標示實際區段。單一模組時兩值相同。`input` 與 `parameters` 分別承載區段資料及該節點解析後的參數。 |
| 追蹤 | Runtime 為每次邏輯 Remote 呼叫產生 `X-Request-Id`，同一呼叫重試時沿用。Runtime 記錄它和入站請求的 [`request_id`](06_runtime_api_and_deployment.md#runtime-request-id)、`run_id` 的對照。`X-Request-Id` 用於追蹤，重試安全性仍取決於操作本身的冪等性。 |
| 成功 | 服務以 2xx 回傳 `{"output": ...}`，Runtime 依有效 System 及區段驗證內容，包括型別、資料識別、向量維度／Profile 與 Inference 語意。 |
| 失敗 | 服務以 4xx 或 5xx 回傳 `error` 物件，其中 `code` 為穩定識別、`message` 為可診斷摘要、`retryable` 為布林值。Runtime 記錄區段、Request ID、狀態及錯誤摘要，遮罩憑證。 |
| 相容 | 同版本可增加外層選填欄位，雙方忽略不認識的外層欄位。`input`／`output` 執行有效 Schema 驗證，`metadata` 保留自由格式。破壞性變更使用新契約版本，既有節點沿用所固定版本。升版過渡期允許現行版與前一版並存。 |

`retryable: false` 禁止重試。`retryable: true` 可列為重試候選。若服務未回有效錯誤封裝，Runtime 以狀態碼分類，429、500、502、503、504 進入重試候選，其他狀態碼結束呼叫。`retryable` 只用於分類，實際重試須同時符合冪等性、剩餘期限及重試預算。無效的 2xx 封裝或輸出是契約錯誤。逾時、連線失敗與空候選分別處理，重試細節見 [Q-017](08_plan_and_decisions.md#q-017)／[Q-028](08_plan_and_decisions.md#q-028)。

| Pipeline | 可替換範圍 | 契約 |
|---|---|---|
| Ingestion | Parsing、Chunking、Embedding 各自可替換，也可選 Parsing → Chunking、Chunking → Embedding、Parsing → Chunking → Embedding | 從 Parsing 開始時 input 是單筆 Document，其餘為同文件 Document[]。output 為 Document[]。涵蓋 Parsing／Chunking 時宣告輸出 structdata，涵蓋 Embedding 時宣告 vectors。 |
| Inference | Query Transformation、Retrieval、Rerank 各自可替換，也可選 Transformation → Retrieval、Retrieval → Rerank、Transformation → Retrieval → Rerank | input／output 皆為 QueryContext[]，候選 Document 遵守從 Ingestion 設定推導的 System Schema。 |

Remote Ingestion 的 `output` 在 Config 中是 Schema 宣告，在 HTTP Response 中是實際 Document 陣列。涵蓋 Parsing 或 Chunking 時，Config 宣告 `output.structdata`。涵蓋 Embedding 時宣告 `output.vectors`，每個向量列出 `source_field`（有效必填字串欄名）、`embedding_profile_id` 及 `dimensions`。同時涵蓋兩類時需要兩份宣告。見 [System Config 欄位](05_system_config.md#config-fields) 與 [Remote API 範例](../examples/user_remote_api/README.md)。

區段只執行一次，涵蓋模組由首節點管理，編譯拒絕重疊。Indexing 與 Inference Input 由平台執行。只替換 Embedding 時，輸出保留原 Document 並附上向量。外部 Retrieval 自行執行搜尋及授權，平台無須等 Ingestion／IndexBinding 就緒。當區段涵蓋 Retrieval，Engine 以共用 I/O 傳入已驗證、合併後的 QueryContext.filters，並驗證回傳候選。過濾、排序及截斷由外部服務決定。未被替換的後段使用驗證過的候選。Inference 區段內的融合、分組和截斷由 Remote 負責，Engine 驗證平台規則與區段不重疊。Remote Retrieval 若留下可識別的 Query／ResultSet，區段外可顯式接平台跨 Query 處理或內建 Rerank。Remote 區段涵蓋到 Inference 最後一個模組時，須回傳恰好一份 Context 及其中一份 ResultSet，否則為契約錯誤。整段 Query Transformation → Rerank 由 Remote 執行時，Runtime 驗證回應及候選契約，按回傳順序交付。平台保留內建擴充的能力，由平台團隊維護方法及相容契約。

業務參數引用 `{{name}}` 優先取已驗證的 Request 值，再取同名 Variable。Remote Ingestion 的引用限 [僅執行期參數](05_system_config.md#parameter-references)。Remote 認證欄位 `auth.bearer_token: "{{KEY}}"` 從 System Secret 取值並組出 `Authorization` Header。服務網址和 Variable 型 Header 只讀 System Variable。Remote Ingestion 的 `revision` 參與索引指紋，服務處理邏輯改變時由使用者更新。

## Ingestion 模組

### Import

依 Import 設定宣告入口欄位與批次參數。Runtime 驗證整批後，在 Parser 前拆成逐文件工作。每個工作帶單筆 Document 及共用參數快照。CSV 每列映射為一筆 Document。

### Parsing

依 System 選定一種內建檔案解析方法或 Remote。結構化資料可直傳，檔案來源依 content 讀取。內建解析保留原始欄位並新增 contenttext，每個解析單位是一筆 Document。解析輸出需保留 `document_id`。入口帶 `source_revision` 時原樣傳遞，省略時維持省略。來源位置選填。

### Chunking

**契約**：同文件的 Document[] → Document[]，輸出各筆具有 data_id，向量在 Embedding 階段加入。[切片識別規則](02_data_contracts.md#document-identities) 適用於內建及 Remote Chunking。每份有效 Chunking 設定只選一個來源欄位，逐 Unit 切分同一欄位。_rag 來源位置與 fingerprint 選填。

**目的與方法**：Fixed-size／Recursive／Header-aware；預設直接切 Document.structdata.text 並寫回 text，不顯示欄位選單、不自動複製其他 fields。進階設定可指定一組 `split_field`／`output_field`，並另外設定要完整複製的欄位。切分輸出及複製欄位的名稱須唯一。metadata 預設全部繼承，不再逐欄勾選。三種方法均以 Token 計量，沿用指定 Tokenizer／revision。2026-10-16 新增的「fix chunk」統一稱 **Fixed-size Chunking（固定 Token 視窗）**；方法已列入需求；Prototype v0.10 有設定展示，正式 Engine／Tokenizer 尚未實作。

| 方法 | 切分依據 | 有效設定 |
|---|---|---|
| Fixed-size | 按固定 Token 視窗切分 | `max_tokens`、`overlap_tokens`、`tokenizer_profile_id`，共用 `split_field`、`output_field`、`copy_fields`。 |
| Recursive | 依分隔符優先序找邊界，過長片段繼續細切 | 共用設定加上 `separators`（分隔符順序）及 `keep_separator`（是否保留分隔符）。`separators` 省略時 Runtime 使用 `["\n\n", "\n", " ", ""]`，此預設不含中文標點。 |
| Header-aware | 先依標題層級切分，超長章節再用 Recursive | 共用設定加上 `header_levels`、標題能力及 Recursive 備援參數。 |

Fixed-size 的邏輯步長為 `size - overlap`；從 Token 0 開始，最後一塊不足 size 時保留、不補齊。視窗涵蓋文件結尾即停止，不再產生只重複末尾 overlap 的多餘 Chunk。例如 Token 串長 11、size=4、overlap=1，半開區間依序為 `[0:4]`、`[3:7]`、`[6:10]`、`[9:11]`；長度為 10 時則在 `[6:10]` 結束。這是 Token 視窗語意例子；Unicode 完整邊界、offset 映射及實際模型輸入重新計數的精確策略仍由 Q-004 核定，不能靠任意 decode Token 片段破壞原文。

**處理**：

1. 檢查切分來源存在且為非空白 string。明確複製的欄位須在上游 Schema 中，複製時沿用型別和必填性。選填欄位缺值時，對應輸出也省略；必填來源缺失、型別錯誤、全空白或零切片時回報明確失敗。
2. 依所選方法切分：Fixed-size 使用上述固定視窗；Recursive 依 separators 優先序切分，必要時處理過長片段，size 是上限、overlap 是目標值。
3. Header-aware 先依可靠標題層級切分，再對超長章節 Recursive；標題取自當筆 Markdown；無標題時依 Component 明確策略處理，不跨 Unit 尋找。
4. 記錄 unit_index 與原 Unit 字串範圍，不從帶 overlap 的文字猜測位置，不跨 Unit 合併。
5. 從同一 Unit 複製指定欄位到 Document.structdata。整包繼承輸入 Document 的 metadata 與可信來源資訊。Component 可選擇提供 metadata._rag.source_refs／chunking，平台保留欄位由 Runtime 管理，見 Q-006。
6. 由 Component 或 SDK helper 產生必要且唯一的 data_id，初始化 vectors={}。fingerprint／ordinal 的 Hash 規則僅為選用參考工具，不強制所有 Component 實作或輸出，見 [資料契約](02_data_contracts.md)～6。

**驗證／例外**：size 為正整數、overlap 為整數且 `0 ≤ overlap < size`、Tokenizer 可用；涵蓋重複文字、非 BMP 字元、空段及極長無分隔文字。Fixed-size 不啟用 separators／keep_separator／header_levels，也不要求 結構化 heading Blocks；未啟用的方法參數可保留草稿，但不驗證或匯出為有效參數。複製欄位未被主要內容切分，不保證其長度小於 size。

**驗收**：單塊不超過約定 Token 上限；offset 可精確還原主要文字；相同輸入與切分設定得到相同 ID；Header-aware 標題能力不足會拒絕。Fixed-size 另驗證零 overlap、短文件、恰好整塊、末塊不足、Unicode、切到結尾不再輸出 overlap-only Chunk，且不因變更停用的 separators／標題層級而改變結果。切換方法、size／overlap 或有效 Tokenizer 屬 Ingestion 配置變更，需重新切分及重建受影響索引。

**待決**：Q-004、Q-005、Q-007；Token 精確計數、切分 fallback 與 overlap 邊界需測試材料。

D-53 的保留完整原文功能已在 Prototype v0.12 以舊 Unit 模型示範，Engine 實作仍待驗收。現行 Chunking 的輸入與輸出使用共用 [Document](02_data_contracts.md)。舊 Unit 的案例見[歷史契約快照](history/superseded/legacy_contracts/README.md)。

<a id="src-04-44-embedding"></a>
### Embedding

**目的**：選 structdata 內容，依 mappings 將 Dense 向量寫入 vectors。多個 output_name 與來源明確對應；與 Indexing 分離。

**處理**：

1. 預設 Embedding Component 可選擇先以模板組合 structdata 與固定文字，寫入獨立衍生欄位（預設 embedding_text），再依映射解析 Profile／服務／Tokenizer 與 document encoding；來源欄位記入向量 source_field。不啟用時沿用原路徑，詳見 [資料契約](02_data_contracts.md)。
2. 對實際來源內容檢查 Token 極限，含前綴及特殊 Token；不能只驗 Chunk Size。
3. 按 Batch Size 呼叫 Embedding Adapter；現有 Prototype 的格式基線為 OpenAI-compatible embeddings。正式首組服務、相容範圍及模型契約仍待 Q-003，不把原型格式當作所有 Embedding API 的通用標準。
4. 驗證回應 index 對應、數量、維度與有限值；不能因回傳順序錯誤把向量寫給其他 Chunk。
5. normalization 與 metric 依 Profile 執行；記錄模型／版本／Provider request ID。
6. 寫回原 Document.vectors 的命名物件（values、embedding_profile_id、source_field），精確格式引用 Document 契約；保留 structdata／metadata。向量映射清單預設一筆 `structdata.text → vectors.text`，可直接新增映射。純全文 Pipeline 不初始化此服務。

**例外**：缺欄位、超長、429／Timeout、批次缺項、維度錯誤與非法數值。截斷或 partial 需明確政策，不能默默處理。

**驗收**：一筆 Chunk 可有兩個具名向量；後續仍取得原文；Query Encoding 依相同 Profile 配對；換模型／維度被判需重建。

**待決**：Q-003、Q-004、Q-009、Q-017。Sparse、多模態及 late interaction 為後續。

<a id="src-04-45-indexing-與搜尋-adapter"></a>
### Indexing 與索引存取

**目的**：保存 Chunk，依欄位用途建索引，回報寫入與可搜尋狀態。Runtime 套用設定時由 Engine 推導索引定義，再由 Elasticsearch 索引存取層建立或接回目標。索引存取層驗證實際 mapping、索引歸屬與相容性指紋，並依 [Runtime 索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle) 執行重建或卸載。

Indexing 保存全部有效 structdata、metadata 與向量。全文與 Filter 能力從 structdata 的有效宣告及 [Indexing 覆寫](05_system_config.md#data-schema-config) 推導，向量能力依逐欄選定的 `vector_fields` 及其 Profile 推導。只保存的 structdata 字串可供 Rerank 或顯示使用，metadata 整包保存供取回。

**處理**：

1. 驗證完整 Chunk 與 fulltext／vector／filter 選擇及 Profile。保存全部 structdata／metadata，並保留 ID、版本和來源資訊。
2. 比較目標 Schema／Profile，拒絕不相容寫入，避免不同模型混在同一向量欄位。
3. 依版本／冪等策略寫入 Chunk，維護 data_id 對照及 Binding。
4. 按後端 refresh／發布規則回報 searchable；write_acknowledged 不等於 searchable。
5. 同一 System／`document_id` 的每次索引寫入使用新的 `write_id`。IndexStore 在第一個 ES Bulk 前於本機記憶體記錄預期 Chunk 與清理範圍，新版完整可搜尋後才清舊。Bulk 回應逾時回報 `ES_BULK_TIMEOUT`，由 Runtime 結案並釋放占用。殘留清理限原批次的 `write_id`。文件存在、清單與 Retire 也使用索引存取層。見 [ES 寫入與清理](06_runtime_api_and_deployment.md#es-write-control-record)。

| 後端 | 內部責任 |
|---|---|
| ES | 組合 Mapping；全文 text、精確 keyword、Dense vector；全部內容可取回但只替選定欄位建立對應搜尋能力；相容查詢及 refresh |
| Local Search（後續） | 每個具名向量管理 FAISS index；每個全文欄位管理 BM25；向量 ID → data_id；完整 Chunk 共用一份 |
| Local／MongoDB（後續） | 保存 Chunk／vectors／Profile Manifest；重啟按相容版本重建搜尋結構，不重新 Parsing／Embedding |

FAISS 的維度／metric 不足以證明向量空間相容。cosine／inner product／L2 的 normalization 與對外 relevance 轉換必須定義；中文 BM25 需斷詞方案。不能把 post-filter 與 Top-K 前授權過濾視為等價。

**驗收**：首版使用 ES。未建搜尋索引的 structdata／metadata 仍完整可取回，巢狀 metadata 整包可取回，全文與 Filter 只使用已啟用的 structdata 欄位。驗證跨 System 隔離、寫入失敗和索引就緒狀態。Local Search 的契約及重啟驗收排入後續。

**待決**：Q-008～Q-013、Q-015；ES 版本／授權 Q-001。

<a id="src-04-5-inference-模組"></a>
## Inference 模組

<a id="src-04-51-query-transformation"></a>
### Query Transformation

**執行方式**：`none` 沿用原始問題，`rewrite` 用同一個 Component 產生一個或多個改寫問題。自訂外部 Query Transformation 使用共用 Remote API Adapter。

**參數**：`llm_ref` 選 System 共用 LLM，`prompt` 可用 `{{query}}` 取得原始問題、`{{count}}` 取得改寫筆數。這兩個模板內建名稱優先於同名參數。其他名稱可用 `{{KEYNAME}}` 引用，依[共用取值規則](05_system_config.md#parameter-references)解析。`count` 是改寫問題的正整數筆數。`include_original` 決定是否另加一筆原始 Query 參與 Retrieval。原始問題始終保存在各 Context 的 `ori_query`。

**輸出**：`none` 輸出一筆原始 Query Context。`rewrite` 依驗證過的改寫字串建立 `QueryContext[]`，保留原始問題、filters 和 metadata，供下游 Retrieval 使用。跨 Query 設定的執行時點見 [結果處理](#result-processing)。

**驗收**：同一 `component_id` 可用 `count=1` 或 `count>1`。`include_original` 由平台套用，模型只需產生改寫字串。`none` 直接使用原始問題。

<a id="src-04-511-討論提案rewrite-的結構化輸出與共用-llm-邊界"></a>
[Rewrite 的模型回應與共用 LLM 提案](08_plan_and_decisions.md#rewrite-output-proposal)

<a id="src-04-512-討論提案合併-rewrite-與-multi-query-設定"></a>
### Rewrite Component 的設定範例

`count=1` 表示單筆改寫，`count>1` 表示多筆改寫。多筆 Prompt 可以要求不同搜尋角度。當設定可能產生多個 Query，Builder 顯示跨 Query 合併設定。模型若實際產生多個有效 Query，Engine 在所選的 Retrieval 或 Rerank 完成後處理。

```yaml
query_transformation:
  component_id: rewrite
  component_version: "1.0.0"
  parameters:
    llm_ref: default-llm
    prompt: "為 {{query}} 產生 {{count}} 個不同的檢索表述。"
    count: 2
    include_original: true
```

這份設定要求兩筆改寫，並讓原始問題一併搜尋。Descriptor 與離線驗證見 [System Config 範例](../examples/system_config/README.md)。Provider 能力與重試依 Q-003／Q-017 另定。首版 Inference 的失敗行為依 Q-023。

<a id="src-04-52-retrieval"></a>
### Retrieval

**目的**：`fulltext_fields` 選已建立全文索引的欄位供 BM25 等全文搜尋，`vector_fields` 選已建立向量索引的欄位。依選擇推導全文／向量／Hybrid，後端由 Binding 繼承。

**處理**：

1. 取得對應 Config／Binding，確認 Profile 與資料就緒。
2. 套用已驗證的 `QueryContext.filters`。Engine 在發布時驗證固定 Filter、在 Inference Input 驗證請求 Filter，兩組以 AND 合併。欄位、運算子、值與 OR 群組遵守 [Filter 契約](02_data_contracts.md#filter-semantics)。
3. 每個 Query 對每個選定的全文或向量欄位建立一條路徑。向量路徑透過 `IndexBinding.vector_bindings[欄位].embedding_profile_id` 使用原索引指定的 Query Encoder。不同向量欄位可沿用各自的 Profile。
4. 每個 Query 的每條內建搜尋路徑先套用完整 Filter，再依 `per_route_k` 取候選，保留路徑、排名、分數及其方向。
5. 同一 Query 若有多條搜尋路徑，須選 RRF 或 Sum Score，以 `data_id` 對齊所有路徑的候選並融合成一份清單。只有一路時，直接使用該路結果。若 Adapter 將融合交給後端，須驗證行為符合選定策略與每路上限。
6. 若設定 `group_by`，先取得所需候選欄位，依[分組代表規則](#group-by-representative)選出每組代表，再執行選填的 Retrieval `top_n`。內建 Retrieval 對每個 Query 交付一份 ResultSet。
7. 在 Rerank／檢索結果消費端使用候選前，批次取回所需 structdata／metadata，保留各路排序與身分；vectors 可省為 {}，下游無須知道 MongoDB 或 FAISS。
8. 跨 Query 規則若選在 Retrieval 後，等 Retrieval 的融合、分組與 Top N 完成，再處理不同 Query 的清單。

Elasticsearch 原生 [RRF](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion) 可在一次搜尋內合併各路共同命中的同一筆 ES hit。不同 Chunk 各有自己的 ES hit，跨查詢請求的結果也各自獨立。覆寫期間，新舊寫入批次可讓同一 `data_id` 有不同實體 `_id`。Adapter 下推融合前須驗證 hit 的身分等同有效 `data_id` 及每路截斷語意，無法保證時由 Engine 依 `data_id` 執行融合。文件層級分組及 Evaluation 仍以 `document_id` 處理。

RRF 與 Sum Score 用於同一 Query 的多路召回。Query Transformation 設定[跨 Query 合併](#cross-query-merge)的執行時點。

Inference 的業務 Input／Output 統一為 `list[QueryContext]`（JSON root array），沒有 InferenceState 外框。QueryContext 固定 ori_query、query，並提供預設空值的 filters、result_sets、metadata。ResultSet 只有 key／items；ResultItem 使用 data 與選填 score。只傳目前有效資料，處理後替換；歷史與診斷寫 Logs。items 順序就是排名，RRF 使用陣列位置。數值 score 經 Adapter 統一為越大越好，Sum Score 仍需驗證完整分數及可比性。 不限制合法流程只能選 Plan A／B。

- Sum Score 以 `sum(weight × relevance_score)` 融合，未命中該路以 0 計。
- RRF 以 `sum(1 / (k + rank))` 融合，排名從 1 開始。兩種策略各自開放的參數及預設值待逐 Component 定義。

原始 BM25 與向量分數可能不同尺度。Sum Score 需要完整且可比的分數或已明確設定的轉換。距離轉換、同分順序及候選截斷的驗收見 Q-011／Q-014。

融合以 `data_id` 對齊候選，分組規則另用 `group_by` 保留代表。融合的分數轉換、同分排序及 Adapter 能力驗收見 [Q-014](08_plan_and_decisions.md#q-014)。

**驗收**：同 Chunk 多路命中按計畫去重；少於 K 或零筆為合法；多路套用相同授權；融合可人工驗算；無效 filter 拒絕而不變無條件搜尋。另驗證逐 Query／跨 Query 與 Rerank 次序、各階段截斷及 Trace；不能只有策略下拉選單而沒有實際路徑變化。

<a id="result-processing"></a>

<a id="src-04-521-resultset-後處理與共同排序"></a>
### ResultSet 後處理與共同排序

| 步驟 | 依設定執行的順序 |
|---|---|
| Retrieval | 每 Query／每路取 `per_route_k` → 多路時以選定的 RRF／Sum Score 合成一份 → 可選 `group_by` → 可選 Retrieval `top_n` |
| Rerank | 每份清單模型評分並重排 → 可選 `group_by` → Rerank Top N |
| 跨 Query | 等所選步驟完成 → 依 `data_id` 取最高分候選並排序 → 可選 `cross_query_group_by` → 可選跨 Query Top N |

<a id="cross-query-merge"></a>
#### 跨 Query 合併

同一原始問題產生兩個以上有效 Query 時，平台合併各 Query 在指定步驟完成後的清單。只有一個有效 Query 時略過。選 Retrieval 後就比較 Retrieval 交付的分數，選 Rerank 後就比較 Rerank 交付的分數。若 Rerank 停用，使用傳到該步驟的既有分數。

依 `data_id` 去重，每個 Chunk 保留分數最高的原候選及其分數，合成一份按分數降冪的清單。同分時依有效 Query 順序及候選在原清單內的順序決定。若設定跨 Query 分組，接著按選定欄位取各組代表，最後才套用跨 Query Top N。

例如 Q1 回傳 A（0.82）、B（0.75），Q2 回傳 A（0.91）、C（0.78）。合併後排序為 A（0.91）、C（0.78）、B（0.75）。若 A 與 B 屬於同一 `document_id`，再按該欄位分組後會留下 A 和 C。

跨 Query 合併的候選須帶有限且可比較的分數。接入 Remote Retrieval 且由平台合併時，服務須提供可辨識的 Query／ResultSet 分組。合併在 Rerank 前執行時，分數由 Retrieval 提供。合併在啟用的 Rerank 後執行時，以 Rerank 結果為準。缺少必要分數或 Adapter 無法提供可比分數時，依 [Inference 失敗契約](06_runtime_api_and_deployment.md#inference-api)回報。

<a id="group-by-representative"></a>
#### 分組代表

`group_by` 在當前每份有序清單中選一個或多個候選 Document 欄位。可選 `document_id` 或 `structdata` 中宣告為 `string` 的欄位。多選時以所有欄位值的組合作為分組鍵，每組保留當前分數最高的候選。同分時保留原排名較前者。有分數的候選優先於無分數的候選，整組均無分數時沿用該清單排名。候選只要有任一選定欄位缺值，就獨立保留。文件去重選 `document_id`。若 Retrieval 以母 Chunk ID 分組，保留的是代表子 Chunk，仍帶自己的 `data_id`。之後可在跨 Query 去重後以 `document_id` 再分組，最後取最終 Top N。

設定位置及候選欄位來源見 [System Config](05_system_config.md#inference-result-processing) 與 [Descriptor](04_component_descriptor.md#group-by-option-source)。

<a id="src-04-53-rerank"></a>
### Rerank

**方法**：None／DEV test use／Rerank API。服務端第一版平台約定：

```json
{"model":"reranker-a","query":"原始問題","documents":["候選 A","候選 B"],"top_n":2}
```

```json
{"results":[{"index":1,"score":0.92},{"index":0,"score":0.61}]}
```

這是平台契約，不是所有模型服務的通用標準。POST 路徑為選定 Base URL 下的 /rerank；其他格式需 Adapter。

**處理**：從選定 ResultSet 的 Document.structdata 取評分內容，保留候選 index 對照；驗證 index 唯一且在範圍內、score 有限，映回相同 Chunk，覆寫目前 score，再排序、套用當步可選的 `group_by`，最後取 Rerank Top N。舊分數不放在業務物件，候選文件與識別沿用輸入。None 略過當步評分、分組與 Top N，跨 Query 規則仍可選在 Rerank 後執行；零筆時直接沿用空清單。跨 Query 合併若已於 Retrieval 後完成，Rerank 用原始問題。若在 Rerank 後才合併，Rerank 可使用各清單對應的當前 Query。服務端 top_n 與平台保留數的邊界如下。

**驗收**：不生成新 data_id；重新 rank；保留原 Retrieval Trace。串接 Timeout／錯誤時不假裝 Rerank=None。

**與最新結果操作的對齊**：Rerank 是「新模型算分」的一種方法；模型輸出經共用排序、可選分組與 Top N，名次由 items 陣列位置表示，不新增 rank 欄位。Top N 保留為可獨立描述的操作能力，但最新 UI 不要求獨立卡片，而是動作的收尾參數；Prototype v0.12 的 Reranker 輸出 Top N 預設 3，見 [Builder UI／Backlog](07_builder_ui.md)。原型 API 說明要求 top_n 等於輸入 documents 數、回應完整評分，再由平台依 UI 上限截斷；正式 Adapter 的完整覆蓋驗證與服務上限仍待 Q-003／Q-014，不能默默依服務預設值少回候選。

**待決**：Q-003、Q-014、Q-017、Q-023；內容欄位分隔、輸入極限、全候選評分與服務回傳缺項政策需核定。

<a id="src-04-54-最終檢索輸出"></a>
### 最終檢索輸出

Inference 在完成配置的 Fusion／Rerank／Top N 後，把 QueryContext[] 收斂成一份最終 Context。流程中可有多份 Context，例如兩筆改寫加原始問題共三份；多 Query 時依[選定時點的合併規則](#cross-query-merge)合併。各 ResultItem 包含 Document 與選填 score，名次由 items 順序表示，無歷史 lineage。

| 最終 Context 欄位 | 交付規則 |
|---|---|
| `ori_query`、`query` | 兩者都是原始問題。實際搜尋的 Query 文字由回應的 `query_variants` 依序列出。 |
| `filters`、`metadata` | 沿用 Inference Input 初始化的值。 |
| `result_sets` | 恰好一份，`key` 為 `final`，items 為最終排名。 |

Runtime HTTP 將最終 Context 放入只含一筆的 `contexts`，保留陣列形狀供日後擴充。逐 Query 清單不放在回應中，後續由診斷介面提供。成功回應及版本欄位見 [Inference API](06_runtime_api_and_deployment.md#inference-api)。

首版若任何必要節點、任一 Query 的搜尋路徑或 Remote 區段最終失敗，整次 Inference 回傳可定位的錯誤。Fusion 使用完整且有效的路徑結果；單路無命中可正常參與融合。全部流程成功但無命中時回空候選。首版的失敗結果與驗收案例見 [Runtime Inference](06_runtime_api_and_deployment.md#src-21-5-inference)。

不呼叫回答生成模型、不建立答案 Prompt／Context Budget，也不回傳模型生成的 answer 或 citations。Embedding、Rewrite 與助手所需服務仍依其各自契約使用。

<a id="541-討論提案預設格式與進階自訂-json-輸出"></a>
舊 相關章節 答案 JSON 格式提案已撤銷；此錨點僅保留供舊文件連結遷移。

<a id="src-04-6-evaluation-邏輯"></a>
## Evaluation 與驗收

<a id="document-level-evaluation"></a>

Evaluation Runner 讀取 Inference 回應的 `contexts`，依資料集驗證排名、來源與無命中行為。標準答案以來源文件 `document_id` 標註相關程度，檢索指標預設按文件排名計算。從指定的最終 ResultSet 保留每份文件排名最前的 Chunk，再以去重後的前 K 份文件計算 Recall@K、MRR 或 nDCG。若只回少量 Chunk，去重後的文件數可能低於 K。評估設定須保留實際候選深度及結果清單的選擇。

以下為標註示意，完整 Dataset 格式及精確指標定義留在 [Q-018](08_plan_and_decisions.md#q-018)。

```json
{
  "query": "散熱孔怎麼清潔？",
  "filters": [],
  "relevant": [
    {"document_id": "guide-1", "grade": 2},
    {"document_id": "guide-7", "grade": 1}
  ]
}
```

需要片段級評估時，以來源欄位及原文片段作為標註基準，文字比對規則由 M6 定義。切分後的 `data_id` 一律排除在評估標註之外。

真實模型、解析、索引、吞吐與隔離另做整合驗收。先使用[現行離線範例](../examples/user_remote_api/README.md)驗證 Document 邊界、Remote 參數、候選相依與錯誤案例。
