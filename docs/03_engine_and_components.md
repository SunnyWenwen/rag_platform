# Engine 與模組

Engine 用固定的 Ingestion／Inference 骨架編譯有效設定。每次執行使用同一 Config Revision，解析相依資源、驗證邊界、執行方法並記錄狀態。Builder、AI 助手與獨立 Runtime 共用設定驗證。平台內部 Registry／Factory 管理已交付的內建方法與 Remote Adapter。

Engine 以 LangGraph 執行共用的 Ingestion／Inference 流程，各 System 傳入該次執行固定的設定快照。Component 接收當次輸入、參數與資源依賴。System 的載入、索引綁定與工作狀態由 [Runtime 管理](06_runtime_api_and_deployment.md#src-07-4-systemrevision-與-engine-生命週期)。

<a id="remote-api"></a>
## User 接入 Remote API

User 提供已部署的 HTTP 服務並在 System 設定完整 Endpoint、認證、連續範圍及參數。Builder 依上游產生 Request Schema，依宣告與共用契約產生 Response Schema。服務以 POST 接收 `{"input": ..., "parameters": {...}}`，回傳 `{"output": ...}`。實際 payload 符合此契約，既有 API 格式的轉接由外部服務處理。

| Pipeline | 可替換範圍 | 契約 |
|---|---|---|
| Ingestion | Parsing、Chunking、Embedding 各自可替換，也可選 Parsing → Chunking、Chunking → Embedding、Parsing → Chunking → Embedding | 從 Parsing 開始時 input 是單筆 Document，其餘為同文件 Document[]。output 為 Document[]。涵蓋 Parsing／Chunking 時宣告輸出 structdata，涵蓋 Embedding 時宣告 vectors。 |
| Inference | Query Transformation、Retrieval、Rerank 各自可替換，也可選 Transformation → Retrieval、Retrieval → Rerank、Transformation → Retrieval → Rerank | input／output 皆為 QueryContext[]，候選 Document 遵守從 Ingestion 設定推導的 System Schema。 |

區段只執行一次，涵蓋模組由首節點管理，編譯拒絕重疊。Indexing 與 Inference Input 由平台執行。只替換 Embedding 時，輸出保留原 Document 並附上向量。外部 Retrieval 自行執行搜尋及授權，平台無須等 Ingestion／IndexBinding 就緒。未被替換的後段使用驗證過的候選。Inference 區段內的融合、分組和截斷由 Remote 負責，Engine 驗證平台規則與區段不重疊。Remote Retrieval 若留下可識別的 Query／ResultSet，區段外可顯式接平台跨 Query 處理或內建 Rerank。整段 Query Transformation → Rerank 由 Remote 執行時，Runtime 驗證回應及候選契約，按回傳順序交付。平台保留內建擴充的能力，由平台團隊維護方法及相容契約。

呼叫前解析 `{{params.name}}` 與固定／動態 Secret reference。實際 Secret 經授權解析後放認證 Header。檢查回應形狀、欄位型別、資料識別、向量維度／Profile 與 Inference 邊界語意。HTTP 錯誤、Timeout、無效 JSON、違反契約及查無候選分別處理。服務失敗的重試依操作冪等性及 Runtime 政策。保留 request ID、模組範圍與錯誤摘要，遮罩憑證。

## Ingestion 模組

### Import

依 Import 設定宣告入口欄位與批次參數。Runtime 驗證整批後，在 Parser 前拆成逐文件工作。每個工作帶單筆 Document 及共用參數快照。CSV 每列映射為一筆 Document。

### Parsing

依 System 選定一種內建檔案解析方法或 Remote。結構化資料可直傳，檔案來源依 content 讀取。內建解析保留原始欄位並新增 contenttext，每個解析單位是一筆 Document。解析輸出需保留 document_id 與來源版本，來源位置選填。

### Chunking

**契約**：同文件的 Document[] → Document[]，輸出各筆具有 data_id，向量在 Embedding 階段加入。每份有效 Chunking 設定只選一個來源欄位，逐 Unit 切分同一欄位。_rag 來源位置與 fingerprint 選填。

**目的與方法**：Fixed-size／Recursive／Header-aware；預設直接切 Document.structdata.text 並寫回 text，不顯示欄位選單、不自動複製其他 fields。進階設定可指定一組 `split_field`／`output_field`，並另外設定要完整複製的欄位。切分輸出及複製欄位的名稱須唯一。metadata 預設全部繼承，不再逐欄勾選。三種方法均以 Token 計量，沿用指定 Tokenizer／revision。2026-10-16 新增的「fix chunk」統一稱 **Fixed-size Chunking（固定 Token 視窗）**；方法已列入需求；Prototype v0.10 有設定展示，正式 Engine／Tokenizer 尚未實作。

| 方法 | 切分依據 | 有效設定 |
|---|---|---|
| Fixed-size | 按固定 Token 視窗前進，不依句子、分隔符或標題找邊界 | size、overlap、tokenizer；共用 split／copy，metadata 預設全部繼承 |
| Recursive | 依分隔符優先序找邊界，過長片段繼續細切 | 共用設定＋separators、keep_separator |
| Header-aware | 先依標題層級切分，超長章節再用 Recursive | 共用設定＋header_levels、標題能力及 Recursive 備援參數 |

Fixed-size 的邏輯步長為 `size - overlap`；從 Token 0 開始，最後一塊不足 size 時保留、不補齊。視窗涵蓋文件結尾即停止，不再產生只重複末尾 overlap 的多餘 Chunk。例如 Token 串長 11、size=4、overlap=1，半開區間依序為 `[0:4]`、`[3:7]`、`[6:10]`、`[9:11]`；長度為 10 時則在 `[6:10]` 結束。這是 Token 視窗語意例子；Unicode 完整邊界、offset 映射及實際模型輸入重新計數的精確策略仍由 Q-004 核定，不能靠任意 decode Token 片段破壞原文。

**處理**：

1. 檢查必要切分欄位存在、為非空白 string，且明確 copy 欄位可取得；來源缺失、型別錯誤、全空白或零切片時回報明確失敗。可選複製第一版不先擴充（D-48）。
2. 依所選方法切分：Fixed-size 使用上述固定視窗；Recursive 依 separators 優先序切分，必要時處理過長片段，size 是上限、overlap 是目標值。
3. Header-aware 先依可靠標題層級切分，再對超長章節 Recursive；標題取自當筆 Markdown；無標題時依 Component 明確策略處理，不跨 Unit 尋找。
4. 記錄 unit_index 與原 Unit 字串範圍，不從帶 overlap 的文字猜測位置，不跨 Unit 合併。
5. 從同一 Unit 複製指定欄位到 Document.structdata；文件摘要保持文件摘要。繼承 輸入 Document 中經 Schema 驗證的全部業務 metadata，並保留必要可信來源／ACL；Component 可選擇提供 metadata._rag.source_refs／chunking，輸入不能覆蓋平台保留資訊，完整可信區協定見 Q-006。第一版不新增 metadata 排除表單，有明確需求再規劃。
6. 由 Component 或 SDK helper 產生必要且唯一的 data_id，初始化 vectors={}。fingerprint／ordinal 的 Hash 規則僅為選用參考工具，不強制所有 Component 實作或輸出，見 [資料契約](02_data_contracts.md)～6。

**驗證／例外**：size 為正整數、overlap 為整數且 `0 ≤ overlap < size`、Tokenizer 可用；涵蓋重複文字、非 BMP 字元、空段及極長無分隔文字。Fixed-size 不啟用 separators／keep_separator／header_levels，也不要求 結構化 heading Blocks；未啟用的方法參數可保留草稿，但不驗證或匯出為有效參數。複製欄位未被主要內容切分，不保證其長度小於 size。

**驗收**：單塊不超過約定 Token 上限；offset 可精確還原主要文字；相同輸入與切分設定得到相同 ID；Header-aware 標題能力不足會拒絕。Fixed-size 另驗證零 overlap、短文件、恰好整塊、末塊不足、Unicode、切到結尾不再輸出 overlap-only Chunk，且不因變更停用的 separators／標題層級而改變結果。切換方法、size／overlap 或有效 Tokenizer 屬 Ingestion 配置變更，需重新切分及重建受影響索引。

**待決**：Q-004、Q-005、Q-007；Token 精確計數、切分 fallback 與 overlap 邊界需測試材料。

D-53 真實 Engine 功能待實作，Prototype v0.12 已有控制與教學預覽：預設 Chunker 可選擇另留每個 Unit 所選欄位的完整原文 Chunk，預設關閉；已有相同完整切片則不重複新增。它與 copy 原文欄位獨立，不跨 Unit 合併，新增結果仍走 Embedding／Indexing 與模型上限檢查。行為與例子見 [Chunk](02_data_contracts.md)。

<a id="src-04-44-embedding"></a>
### Embedding

**目的**：選 structdata 內容，依 mappings 將 Dense 向量寫入 vectors。多個 output_name 與來源明確對應；與 Indexing 分離。

**處理**：

1. 預設 Embedding Component 可選擇先以模板組合 structdata 與固定文字，寫入獨立衍生欄位（預設 embedding_text），再依映射解析 Profile／服務／Tokenizer 與 document encoding；來源欄位記入向量 source_field。不啟用時沿用原路徑，詳見 [資料契約](02_data_contracts.md)。
2. 對實際來源內容檢查 Token 極限，含前綴及特殊 Token；不能只驗 Chunk Size。
3. 按 Batch Size 呼叫 Embedding Adapter；現有 Prototype 的格式基線為 OpenAI-compatible embeddings。正式首組服務、相容範圍及模型契約仍待 Q-003，不把原型格式當作所有 Embedding API 的通用標準。
4. 驗證回應 index 對應、數量、維度與有限值；不能因回傳順序錯誤把向量寫給其他 Chunk。
5. normalization 與 metric 依 Profile 執行；記錄模型／版本／Provider request ID。
6. 寫回原 Document.vectors 的命名物件（values、embedding_profile_id、source_field），精確格式引用 Document 契約；保留 structdata／metadata。預設 structdata.text → vectors.text，其他映射由進階設定；純全文 Pipeline 不初始化此服務。

**例外**：缺欄位、超長、429／Timeout、批次缺項、維度錯誤與非法數值。截斷或 partial 需明確政策，不能默默處理。

**驗收**：一筆 Chunk 可有兩個具名向量；後續仍取得原文；Query Encoding 依相同 Profile 配對；換模型／維度被判需重建。

**待決**：Q-003、Q-004、Q-009、Q-017。Sparse、多模態及 late interaction 為後續。

<a id="src-04-45-indexing-與搜尋-adapter"></a>
### Indexing 與索引存取

**目的**：保存 Chunk，依欄位用途建索引，回報寫入與可搜尋狀態。Runtime 套用設定時由 Engine 推導索引定義，再由 Elasticsearch 索引存取層建立或接回目標。索引存取層驗證實際 mapping、索引歸屬與相容性指紋，並依 [Runtime 索引生命週期](06_runtime_api_and_deployment.md#system-index-lifecycle) 執行重建或卸載。

**2026-10-16 已確認的簡化**：預設保存 Chunk 的全部 structdata／metadata，不再要求使用者填 stored_fields 或勾「儲存內容」。保存內容與建立搜尋索引分開：使用者只選全文欄位、向量欄位與可過濾欄位；未選搜尋索引的 title 等欄位仍可供 Rerank／檢索結果消費端／引用使用。保留 metadata 不代表自動對所有 metadata 建立 Filter／全文索引。向量保存與恢復沿用既有完整 Chunk／vectors 政策，不因拿掉內容選單而刪除 vectors。

**處理**：

1. 驗證完整 Chunk 與 fulltext／vector／filter 選擇及 Profile；全部 structdata／metadata 保存，ID／版本／來源／ACL 固定保留，不再以使用者的保存投影刪欄位。
2. 比較目標 Schema／Profile，拒絕不相容寫入，避免不同模型混在同一向量欄位。
3. 依版本／冪等策略寫入 Chunk，維護 data_id 對照及 Binding。
4. 按後端 refresh／發布規則回報 searchable；write_acknowledged 不等於 searchable。
5. 同一 System／`document_id` 以一次 `write_id` 寫入新版。新版全部成功且可搜尋後，才清理舊批次。若確認新版寫入失敗，只清理本次批次。文件存在、清單與 retire 也使用索引存取層。詳見 [Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。

| 後端 | 內部責任 |
|---|---|
| ES | 組合 Mapping；全文 text、精確 keyword、Dense vector；全部內容可取回但只替選定欄位建立對應搜尋能力；相容查詢及 refresh |
| Local Search | 每個具名向量管理 FAISS index；每個全文欄位管理 BM25；向量 ID → data_id；完整 Chunk 共用一份 |
| Local／MongoDB | 保存 Chunk／vectors／Profile Manifest；重啟按相容版本重建搜尋結構，不重新 Parsing／Embedding |

FAISS 的維度／metric 不足以證明向量空間相容。cosine／inner product／L2 的 normalization 與對外 relevance 轉換必須定義；中文 BM25 需斷詞方案。不能把 post-filter 與 Top-K 前授權過濾視為等價。

**驗收**：ES 與 Local 共用契約測試；未建搜尋索引的 structdata／metadata 仍完整可取回；metadata 不因未勾可過濾而遺失；只有宣告的欄位可搜尋／過濾；不出現跨 System Chunk；寫入失敗／不就緒不回可查詢；Memory 重啟清空、MongoDB 可驗證恢復。

**待決**：Q-008～Q-013、Q-015；ES 版本／授權 Q-001。

<a id="src-04-5-inference-模組"></a>
## Inference 模組

<a id="src-04-51-query-transformation"></a>
### Query Transformation

**執行方式**：`none` 沿用原始問題，`rewrite` 用同一個 Component 產生一個或多個改寫問題。自訂外部 Query Transformation 使用共用 Remote API Adapter。

**參數**：`llm_ref` 選 System 共用 LLM，`prompt` 可引用 `{{query}}`、`{{count}}` 及已宣告的 `{{params.name}}`。`count` 是改寫問題的正整數筆數。`include_original` 決定是否另加一筆原始 Query 參與 Retrieval。原始問題始終保存在各 Context 的 `ori_query`。

**輸出**：`none` 輸出一筆原始 Query Context。`rewrite` 依驗證過的改寫字串建立 `QueryContext[]`，保留原始問題、filters 和 metadata，供下游 Retrieval 使用。跨 Query 設定的執行時點見 [結果處理](#result-processing)。

**驗收**：同一 `component_id` 可用 `count=1` 或 `count>1`。`include_original` 由平台套用，模型只需產生改寫字串。`none` 直接使用原始問題。

<a id="src-04-511-討論提案rewrite-的結構化輸出與共用-llm-邊界"></a>
### 討論提案：Rewrite 的結構化輸出與共用 LLM 邊界

**狀態：2026-10-16 提案，待使用者確認及 Q-003／Q-017／Q-023 核定；不是已實作或已凍結的公共 Contract。** 建議 UI 加單模組試跑，見 Builder UI／Backlog手冊／UI Backlog手冊；輸出形狀與數量由平台提供，Prompt 主要描述如何改寫，不讓使用者每次重寫機器可讀契約。

Rewrite 的模型回應草案為 `{queries: [...]}`，由 `count` 決定所需筆數。原始問題及 include_original 由平台處理，與模型要求生成的數量分開。ori_query、filters、metadata 由 Runtime 保留／複製，LLM 只生成 query 文字，不負責授權或結果物件。

以下 Python／Pydantic 例子只示範按 n 產生 Schema 及驗證形狀／型別／數量，不會呼叫 LLM；可將匯出的 JSON Schema 交給支援的 Provider。正式類別名稱與 Adapter 格式仍待決：

```python
from pydantic import ConfigDict, Field, StrictStr, create_model

def rewrite_result_schema(n: int):
    if n < 1:
        raise ValueError("n must be positive")
    return create_model(
        f"RewriteResult{n}",
        __config__=ConfigDict(extra="forbid"),
        queries=(list[StrictStr], Field(..., min_length=n, max_length=n)),
    )

Result = rewrite_result_schema(3)
schema = Result.model_json_schema()  # queries: minItems=3, maxItems=3
result = Result.model_validate({"queries": [
    "設備的建議清潔週期為何？",
    "多久應清潔一次設備？",
    "設備清潔保養的頻率是什麼？",
]})
```

建議的處理責任：

1. **模組定義輸出 Schema**：固定 key、型別與要求筆數；使用者改 Prompt 不改這個契約。
2. **共用 LLM Adapter 選擇能力**：優先使用 Provider 原生 Structured Output；支援工具呼叫者可用指定的結構化回傳工具；僅有文字／JSON mode 時解析後嚴格驗證，不宣稱同等約束。OpenAI-compatible URL 不代表服務／模型支援相同功能，須實測 Profile／能力；不支援時明確報錯或用已核定策略，不靜默換模式。
3. **Engine 做語意驗證**：解析、額外 key、實際筆數、去除首尾空白後非空、重複及原始問題政策。上例沒有自動完成非空／重複檢查；正規化後仍須符合目標筆數。是否允許與原始問題相同、等價重複與最終 Query 去重規則仍由 Q-003／Q-023 核定，不用補複製 Query 或任意截掉多餘結果來假裝符合數量。
4. **失敗政策**：格式錯誤可在核定次數／時間／成本上限內重試或修正；拒答、回應截斷、Timeout 等分開處理。耗盡後回可定位的模組錯誤，或採明確核定的 fallback，不能無限重試或未告知改回原始問題。

這套邊界可共用，但每個用途的輸出 Schema 不同：

| 用途 | 建議模型輸出 | 後端驗證 |
|---|---|---|
| Rewrite | queries 的 count 筆字串清單 | 數量、非空、重複、原始問題保存 |
| AI 設定助手 | Config 草稿、建議／Diff、缺項 | Schema、Registry、欄位相依與草稿基準 |

服務連線與模型引用集中管理，Schema 由每次模組呼叫傳入，不在同一 LLM 服務上固定一種輸出格式。使用 LangChain 時可採其 Model structured-output 介面，不需要為單次 Rewrite 引入完整 Agent。

官方依據（查核 2026-10-16）：[JSON Schema 的陣列長度限制](https://json-schema.org/understanding-json-schema/reference/array#length)；[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 說明 Schema 約束與 JSON mode 的區別、支援子集及拒答／不完整回應；[LangChain Models](https://docs.langchain.com/oss/python/langchain/models)／[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output) 說明 Provider／Tool 策略與驗證。來源提供技術依據，不直接核定本專案的 Provider、類別、重試數或 fallback 預設。

<a id="src-04-512-討論提案合併-rewrite-與-multi-query-設定"></a>
### Rewrite Component 的設定範例

`count=1` 表示單筆改寫，`count>1` 表示多筆改寫。多筆 Prompt 可以要求不同搜尋角度。當設定可能產生多個 Query，Builder 顯示跨 Query 融合設定。模型若實際產生多個有效 Query，Engine 在所選的 Retrieval 或 Rerank 完成後處理。

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

這份設定要求兩筆改寫，並讓原始問題一併搜尋。Descriptor 與離線驗證見 [System Config 範例](../examples/system_config/README.md)。Provider 能力、重試與 fallback 依 Q-003／Q-017／Q-023 另定。

<a id="src-04-52-retrieval"></a>
### Retrieval

**目的**：`fulltext_fields` 選已建立全文索引的欄位供 BM25 等全文搜尋，`vector_fields` 選已建立向量索引的欄位。依選擇推導全文／向量／Hybrid，後端由 Binding 繼承。

**處理**：

1. 取得對應 Config／Binding，確認 Profile 與資料就緒。
2. 將預設 filters、本次 filters、可信 ACL 以 AND 合併。從可過濾欄位選路徑，以 `eq`／`in` 設定條件，值依欄位宣告型別驗證。Data Column 的型別及各類能力標記另行定義。
3. 建立每個 Query × 全文／向量欄位的路徑；向量路徑依其 Profile 使用 query encoding。
4. 每個 Query 的每條搜尋路徑先依 `per_route_k` 取候選，保留路徑、排名、分數及其方向。
5. 同一 Query 若有多條搜尋路徑，須選 RRF 或 Sum Score，以 `data_id` 對齊所有路徑的候選並融合成一份清單。只有一路時，直接使用該路結果。若 Adapter 將融合交給後端，須驗證行為符合選定策略與每路上限。
6. 若設定 `group_by`，先取得所需候選欄位，依當前排名分組，再執行選填的 Retrieval `top_n`。內建 Retrieval 對每個 Query 交付一份 ResultSet。
7. 在 Rerank／檢索結果消費端使用候選前，批次取回所需 structdata／metadata，保留各路排序與身分；vectors 可省為 {}，下游無須知道 MongoDB 或 FAISS。
8. 跨 Query 規則若選在 Retrieval 後，等 Retrieval 的融合、分組與 Top N 完成，再處理不同 Query 的清單。

已確認同 Query 的多路融合屬於 Retrieval。跨 Query 融合由 Query Transformation 的設定入口選擇在 Retrieval 或 Rerank 的末尾執行。先逐 Query Sum Score、再跨 Query RRF 是可表達情境。

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
| 跨 Query | 等所選步驟完成 → 跨 Query 融合 → 可選 `group_by` → 可選跨 Query Top N |

跨 Query 融合以同一原始問題為範圍，將各 Query 已完成當步處理的清單合併。若接入 Remote Retrieval 且平台負責跨 Query 融合，服務須提供可辨識的 Query／ResultSet 分組。只有一個有效 Query 時略過跨 Query 規則。若選 `after_rerank` 且 Rerank 為 None，跨 Query 使用到達該時點的清單及排名。

### 分組代表

`group_by` 在當前每份有序清單中選一個或多個候選 Document 欄位。多選時以所有欄位值的組合為分組鍵，每組保留排名最高的一筆。候選只要有任一選定欄位缺值或為 null，就獨立保留。文件去重選 `document_id`。若 Retrieval 以母 Chunk ID 分組，保留的是代表子 Chunk，仍帶自己的 `data_id`。之後可在跨 Query 融合後以 `document_id` 再分組，最後取最終 Top N。

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

**處理**：從選定 ResultSet 的 Document.structdata 取評分內容，保留候選 index 對照；驗證 index 唯一且在範圍內、score 有限，映回相同 Chunk，覆寫目前 score，再排序、套用當步可選的 `group_by`，最後取 Rerank Top N。舊分數不放在業務物件，不改文件／ACL 或生成新候選。None 略過當步評分、分組與 Top N，跨 Query 規則仍可選在 Rerank 後執行；零筆時直接沿用空清單。跨 Query 融合若已於 Retrieval 後完成，Rerank 用原始問題；若在 Rerank 後才融合，Rerank 可使用各清單對應的當前 Query。服務端 top_n 與平台保留數的邊界如下。

**驗收**：不生成新 data_id；重新 rank；保留原 Retrieval Trace。串接 Timeout／錯誤時不假裝 Rerank=None。

**與最新結果操作的對齊**：Rerank 是「新模型算分」的一種方法；模型輸出經共用排序、可選分組與 Top N，名次由 items 陣列位置表示，不新增 rank 欄位。Top N 保留為可獨立描述的操作能力，但最新 UI 不要求獨立卡片，而是動作的收尾參數；Prototype v0.12 的 Reranker 輸出 Top N 預設 3，見 [Builder UI／Backlog](07_builder_ui.md)。原型 API 說明要求 top_n 等於輸入 documents 數、回應完整評分，再由平台依 UI 上限截斷；正式 Adapter 的完整覆蓋驗證與服務上限仍待 Q-003／Q-014，不能默默依服務預設值少回候選。

**待決**：Q-003、Q-014、Q-017、Q-023；內容欄位分隔、輸入極限、全候選評分與服務回傳缺項政策需核定。

<a id="src-04-54-最終檢索輸出"></a>
### 最終檢索輸出

Inference 在完成配置的 Fusion／Rerank／Top N 後，直接回傳 QueryContext[]；各 ResultItem 包含 Document 與選填 score，名次由 items 順序表示，無歷史 lineage。跨 Query 合併停用時保留分組結果，不任意再融合一次。API 包裝見 [Runtime API／部署](06_runtime_api_and_deployment.md#src-07-3-平台管理資料與儲存)，最終結果選擇與版本政策仍由 Q-014／Q-019 核定。

不呼叫回答生成模型、不建立答案 Prompt／Context Budget，也不回傳模型生成的 answer 或 citations。Embedding、Rewrite 與助手所需服務仍依其各自契約使用。

<a id="541-討論提案預設格式與進階自訂-json-輸出"></a>
舊 相關章節 答案 JSON 格式提案已撤銷；此錨點僅保留供舊文件連結遷移。

<a id="src-04-6-evaluation-邏輯"></a>
## Evaluation 與驗收

Evaluation Runner 重用 Inference 契約，依資料集驗證排名、來源與無命中行為。真實模型、解析、索引、吞吐與隔離另做整合驗收。先使用[現行離線範例](../examples/user_remote_api/README.md)驗證 Document 邊界、Remote 參數、候選相依與錯誤案例。
