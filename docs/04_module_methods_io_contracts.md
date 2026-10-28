# RAG Engine — 組裝、執行與模組開發規格

> 文件集 v0.19 · 2026-10-16 · 開發規格草案
>
> 本文涵蓋可獨立執行的 Engine 與各模組；正式名詞定義見 [03 §3](../03_architecture_proposal.md#terminology)，共用資料／Config 結構見 05。既有產品語意為已確認方向，新增 SDK、Registry 形狀、執行政策為建議，須經對應 Q-ID 核定。本次未新增 Engine 程式。

> 2026-10-28 補充 Module Developer 擴充規劃：本文負責 Engine 必須提供的機制與限制；[11 Method 開發指南](11_method_developer_guide.md) 負責開發、測試與交付流程。開放 Method 開發是需求方向，以下公開介面、套件結構及載入方式仍為設計草案；本輪不凍結 ParsedDocument 等待決 Schema。

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

### 1.1 SDK、Engine 與 Method package

| 元件 | 職責 | 依賴邊界 |
|---|---|---|
| `rag-engine-sdk`（暫名） | 共用 I/O 型別、各 Module 的公開介面、Config 驗證與受控 RunContext；另規劃契約測試工具 | 不依賴 Engine 私有實作或 Builder；資料形狀以 05 為準 |
| `rag-engine`（暫名） | Registry、相容性驗證、Pipeline 組裝、生命週期、執行政策與資源管理 | 使用 SDK 契約，載入已安裝且核可的 Method package |
| rag_engine 內的 Method package | 實作一個或多個 Module 的 Method，附設定、能力宣告、測試與說明 | 依賴 SDK 公開介面及自身必要套件；不依賴 Builder 或 Engine 私有類別 |

內建與開發者提供的 Method 應遵循相同公開契約與語意檢查，不能以內建方法的私有捷徑作為唯一可行用法。2026-10-28 已確認：SDK、Engine、所有 Methods／Adapters 與 Runtime API 同放 `rag_engine` repo，Builder 前後端放 `rag_platform`，見 [03 §3.7](../03_architecture_proposal.md#repository-boundaries)。Module Developer 在 methods 目錄提交 PR，不要求另建 Method repo；同一 package 可包含成對的 Indexing／Retrieval。套件邊界仍保留，精確名稱／目錄由 Q-001 核定。

SDK 的「獨立」是可安裝、可依賴的公開邊界；不表示 Method 的完整 Engine 整合測試不需要 Engine。單方法測試可用 SDK 測試工具與資源替身，整合測試使用同一交付版本中的相容 Engine。Engine 與 Method packages 共同納入完整 Runtime Image；不以拆出另一個 Methods 服務作為首期執行模型。

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

建議每個註冊方法提供 module_type、method_id、implementation_version、input_schema、output_schema、config_schema、requires、provides、supports 及 factory。由 Engine 編譯器串接，不由 Builder 寫另一套組裝流程。

本節將原草案中表示方法的 `module_id` 統一稱為 `method_id`：`module_type` 表示職責，例如 chunking；`method_id` 表示具體方法，例如 team_a.chunking.custom；Python class 名稱只是實作符號。同一方法可以用不同參數建立多個實例，不需要因此新增 method_id。這次只對齊 Registry 設計用語；正式 Config 欄位、舊別名與遷移仍由 Q-002 核定，不改既有 Prototype／公開 Schema。

```yaml
method_id: company.chunking.recursive
module_type: chunking
implementation_version: 1.0.0
contract_version: 0.1-draft
requires: [document.string_field, tokenizer]
provides: [chunk.fields, chunk.locations]
supports: {async: true, batch: true, streaming: false}
```

宣告能力須有契約測試。Registry 須可追溯 distribution package 名稱／版本、Method 實作版本、SDK／Engine 相容範圍與 Contract 版本。`method_id + implementation_version` 在同一有效 Registry 內不能對應兩份不同實作；重複註冊應明確失敗，不能由載入先後決定覆蓋。

### 2.4 套件安裝、發現與載入

建議流程：從 rag_engine 同一交付版本建置 SDK／Engine／核可 Method packages → 在開發環境或 Runtime Image 建置時安裝 → 發現與核對核可清單／版本 → 載入並註冊 → 驗證 Config 的方法與相依能力 → 建立實例。**repo 是原始碼來源，安裝 package 才提供 Python import 的程式，Registry 則負責方法查找；三者不可互相取代。**

- 本機開發可使用 editable install；DEV 與 FTEST／ENT 交付使用可追溯的固定套件與 Image。執行 Ingestion／Query 時不由 Config 任意下載 repo 或安裝套件。
- 同 repo 的 Methods 仍安裝到 Engine 使用的 Python 環境，透過同一 Registry 註冊；建立目錄不等於初始化所有方法／外部服務，依有效 Config 初始化所選方法。Builder 透過 Runtime API 及方法目錄使用它們，不須在 Builder Image 安裝全部 Method packages。
- 初期可明確 import／register；後續建議以 Python entry points 發現核可套件，沿用同一 Registry。具體 entry point group、Factory 介面及錯誤格式留 Q-001／Q-002／Q-022。
- 核對發行套件及載入政策應在 import／entry point load 前進行；import 本身可能執行程式。已安裝、被發現、通過契約與允許執行是不同狀態。
- Config 用方法識別與有效參數選擇實作，不接受任意 Python import path。完整版本解析結果需保存於可追溯的執行／交付紀錄；放在 Config 或相伴鎖定檔的精確格式留 Q-002／Q-015／Q-021。
- 找不到方法、版本不相容、能力不足或索引不相容時，回傳含模組／方法的可定位錯誤；不得自動改用其他方法或最新版本。失敗釋放初始化資源。

Package 版本與 Method 實作版本不一定一對一；一個 package 可交付多個 Method。首版不承諾同一 Python 程序並存同一 package 的多個版本；不相容依賴可先由不同 Runtime Image／環境承載，具體路由與共存政策仍待決。

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

**目的與方法**：Fixed-size／Recursive／Header-aware；一個主要 split_field＋多個 copy_fields，metadata 預設全部繼承，不再逐欄勾選。三種方法均以 Token 計量，沿用指定 Tokenizer／revision。2026-10-16 新增的「fix chunk」統一稱 **Fixed-size Chunking（固定 Token 視窗）**；方法已列入需求，Engine 與 Prototype 尚未因此實作。

| 方法 | 切分依據 | 有效設定 |
|---|---|---|
| Fixed-size | 按固定 Token 視窗前進，不依句子、分隔符或標題找邊界 | size、overlap、tokenizer；共用 split／copy，metadata 預設全部繼承 |
| Recursive | 依分隔符優先序找邊界，過長片段繼續細切 | 共用設定＋separators、keep_separator |
| Header-aware | 先依標題層級切分，超長章節再用 Recursive | 共用設定＋header_levels、標題能力及 Recursive 備援參數 |

Fixed-size 的邏輯步長為 `size - overlap`；從 Token 0 開始，最後一塊不足 size 時保留、不補齊。視窗涵蓋文件結尾即停止，不再產生只重複末尾 overlap 的多餘 Chunk。例如 Token 串長 11、size=4、overlap=1，半開區間依序為 `[0:4]`、`[3:7]`、`[6:10]`、`[9:11]`；長度為 10 時則在 `[6:10]` 結束。這是 Token 視窗語意例子；Unicode 完整邊界、offset 映射及實際模型輸入重新計數的精確策略仍由 Q-004 核定，不能靠任意 decode Token 片段破壞原文。

**處理**：

1. 檢查主要欄位為非空必填 string、copy 欄位可取得。
2. 依所選方法切分：Fixed-size 使用上述固定視窗；Recursive 依 separators 優先序切分，必要時處理過長片段，size 是上限、overlap 是目標值。
3. Header-aware 先依可靠標題層級切分，再對超長章節 Recursive；缺 headings 不能假裝成功。
4. 計算原 fields 字串範圍及跨 block／page locations，不從帶 overlap 的文字猜測位置。
5. 複製指定 fields；文件摘要保持文件摘要。繼承 ParsedDocument 中經 Schema 驗證的全部業務 metadata，並保留／加入可信來源、ACL、片段 locations；輸入不能覆蓋平台保留資訊，精確命名見 Q-006。第一版不新增 metadata 排除表單，有明確需求再規劃。
6. 依有效切分設定及位置產生 chunk_id，初始化 vectors={}。

**驗證／例外**：size 為正整數、overlap 為整數且 `0 ≤ overlap < size`、Tokenizer 可用；涵蓋重複文字、非 BMP 字元、空段及極長無分隔文字。Fixed-size 不啟用 separators／keep_separator／header_levels，也不要求 Parser headings；未啟用的方法參數可保留草稿，但不驗證或匯出為有效參數。複製欄位未被主要內容切分，不保證其長度小於 size。

**驗收**：單塊不超過約定 Token 上限；offset 可精確還原主要文字；相同輸入與切分設定得到相同 ID；Header-aware 標題能力不足會拒絕。Fixed-size 另驗證零 overlap、短文件、恰好整塊、末塊不足、Unicode、切到結尾不再輸出 overlap-only Chunk，且不因變更停用的 separators／標題層級而改變結果。切換方法、size／overlap 或有效 Tokenizer 屬 Ingestion 配置變更，需重新切分及重建受影響索引。

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

**2026-10-16 已確認的簡化**：預設保存 Chunk 的全部 fields／metadata，不再要求使用者填 stored_fields 或勾「儲存內容」。保存內容與建立搜尋索引分開：使用者只選全文欄位、向量欄位與可過濾欄位；未選搜尋索引的 title 等欄位仍可供 Rerank／Generation／引用使用。保留 metadata 不代表自動對所有 metadata 建立 Filter／全文索引。向量保存與恢復沿用既有完整 Chunk／vectors 政策，不因拿掉內容選單而刪除 vectors。

**處理**：

1. 驗證完整 Chunk 與 fulltext／vector／filter 選擇及 Profile；全部 fields／metadata 保存，ID／版本／來源／ACL 固定保留，不再以使用者的保存投影刪欄位。
2. 比較目標 Schema／Profile，拒絕不相容寫入，避免不同模型混在同一向量欄位。
3. 依版本／冪等策略寫入 Chunk，維護 chunk_id 對照及 Binding。
4. 按後端 refresh／發布規則回報 searchable；write_acknowledged 不等於 searchable。
5. 更新／刪除與舊版本清除依 Q-008／Q-009；尚未核定不能自行宣告文件原子替換。

| Adapter | 內部責任 |
|---|---|
| ES | 組合 Mapping；全文 text、精確 keyword、Dense vector；全部內容可取回但只替選定欄位建立對應搜尋能力；相容查詢及 refresh |
| Local Search | 每個具名向量管理 FAISS index；每個全文欄位管理 BM25；向量 ID → chunk_id；完整 Chunk 共用一份 |
| Local／MongoDB | 保存 Chunk／vectors／Profile Manifest；重啟按相容版本重建搜尋結構，不重新 Parsing／Embedding |

FAISS 的維度／metric 不足以證明向量空間相容。cosine／inner product／L2 的 normalization 與對外 relevance 轉換必須定義；中文 BM25 需斷詞方案。不能把 post-filter 與 Top-K 前授權過濾視為等價。

**驗收**：ES 與 Local 共用契約測試；未建搜尋索引的 fields／metadata 仍完整可取回；metadata 不因未勾可過濾而遺失；只有宣告的欄位可搜尋／過濾；不出現跨 System Chunk；寫入失敗／不就緒不回可查詢；Memory 重啟清空、MongoDB 可驗證恢復。

**待決**：Q-008～Q-013、Q-015；ES 版本／授權 Q-001。

## 5. Inference 模組

### 5.1 Query Transformation

**方法**：None／Rewrite／Multi-query；原始問題永遠保留。count 指衍生 Query 數，不含選配原始問題。

**處理**：None 回一筆原始 Query；Rewrite 使用 {{query}} 產生一筆；Multi-query 使用 {{query}}／{{count}} 產生多筆。include_original 由程式處理，不交由 Prompt 決定。引用 System 共用 llm_ref。

**驗證**：非空問題、合法模板、LLM 引用、衍生結果數量／文字合法。去除相同問題、模型輸出格式不符及降級政策由 Q-003／Q-023 核定；不自動忽略壞結果。

**驗收**：Rewrite 不覆蓋 original_question；Multi-query count 與原始問題選項獨立；None 不呼叫 LLM；Rerank／Generation 始終取得原始問題。

### 5.1.1 討論提案：Rewrite 的結構化輸出與共用 LLM 邊界

**狀態：2026-10-16 提案，待使用者確認及 Q-003／Q-017／Q-023 核定；不是已實作或已凍結的公共 Contract。** 建議 UI 加單模組試跑，見 06／10；輸出形狀與數量由平台提供，Prompt 主要描述如何改寫，不讓使用者每次重寫機器可讀契約。

建議 Rewrite 與 Multi-query 共用 `{queries: [...]}` 的結果形狀；Rewrite 目標為 1 筆，Multi-query 目標為 Config.count 筆。原始問題及 include_original 由平台處理，與模型要求生成的數量分開。query_id、ori_query、source_query_ids 等執行資料也由 Engine 建立，不要求 LLM 自行填入或維護身分。

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
| Rewrite／Multi-query | queries 的 1／N 筆字串清單 | 數量、非空、重複、原始問題保存 |
| AI 設定助手 | Config 草稿、建議／Diff、缺項 | Schema、Registry、欄位相依與草稿基準 |
| Generation | 預設回答文字由平台包裝；進階自訂 JSON 提案見 §5.4.1 | 引用來自真實 Context；業務內容 Schema、主要回答欄位與 API／Streaming 契約分開 |

服務連線與模型引用集中管理，Schema 由每次模組呼叫傳入，不在同一 LLM 服務上固定一種輸出格式。使用 LangChain 時可採其 Model structured-output 介面，不需要為單次 Rewrite 引入完整 Agent。

官方依據（查核 2026-10-16）：[JSON Schema 的陣列長度限制](https://json-schema.org/understanding-json-schema/reference/array#length)；[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 說明 Schema 約束與 JSON mode 的區別、支援子集及拒答／不完整回應；[LangChain Models](https://docs.langchain.com/oss/python/langchain/models)／[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output) 說明 Provider／Tool 策略與驗證。來源提供技術依據，不直接核定本專案的 Provider、類別、重試數或 fallback 預設。

### 5.1.2 討論提案：合併 Rewrite 與 Multi-query 設定

**2026-10-16 10:22 提問後的建議，待確認。** 現有 Prototype v0.9 有 None／Rewrite／Multi-query；Rewrite 固定一筆，Multi-query 使用 count，且分別保存 rewrite_prompt／multi_prompt。兩者目前不是只有畫面名稱不同，也尚無真實 Engine 生成實作。不要把共用輸出 Schema 提案描述成現有已共用的執行程式。

建議保留同一 Query Transformation 模組，UI 簡稱 Query Rewrite，以啟用／停用、產生 Query 數量 N、include_original、llm_ref 與一份有效 Prompt 控制：N=1 表示單 Query 改寫，N>1 表示多個檢索表述，停用則直接沿用原始問題、不呼叫模型。多筆時 Prompt 建議描述不同表述／搜尋角度，不能只靠改數字就保證多樣性。

數量設定由平台動態帶入 Schema，queries 的 minItems／maxItems 同為 N，並供實際 Provider 支援的結構化生成與後端驗證使用。Prompt 可自由描述改寫內容，格式／型別／筆數則由平台的 I/O 契約管理；可提供 query／count 變數及固定格式要求預覽，但不依靠使用者手寫「輸出幾筆」才建立限制。Prompt 與設定衝突時仍只放行通過 Schema／語意驗證的結果，不能讓 Prompt 覆寫所選 count。語法與筆數合格不代表保留原意或足夠多樣，後者需人工／Evaluation 驗證。

此為單一方法與共用執行邏輯的候選，不新增另一個 Pipeline 模組。舊 Rewrite 映射 N=1，舊 Multi-query 保留原 count；取原先啟用的 Prompt 為新有效 Prompt，另一份舊草稿的保留／可恢復政策需 Q-002 核定，不能靜默刪除。None、include_original、LLM 引用、逐 Query／跨 Query 融合語意維持一致。採用後應同步 SDK、Registry、AI 助手、UI、範例與驗證；本輪只記提案，不更動原型／正式 Config 枚舉。

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

### 5.4.1 討論提案：預設格式與進階自訂 JSON 輸出

**2026-10-16 10:22 提案，待確認；尚未實作。** 建議保留現有 Generation 模組與基本操作，預設輸出「回答文字＋平台引用」。進階輸出設定預設收合、自訂 JSON 未啟用；展開說明不改 Config。需要機器處理欄位時，使用者明確啟用並編輯回答內容的 JSON Schema，不另加一次 LLM 格式化呼叫或 Output 模組。

以下僅示範 **Generation 的業務內容**，不是整個 HTTP 回應，也不是已凍結的模型／API 格式。預設內容可理解為：

```json
{"answer": "依規範，建議每月清潔設備。"}
```

使用者有需要時可定義：

```json
{"summary": "建議每月清潔設備。", "steps": ["關機並切斷電源", "清除散熱孔灰塵"]}
```

對應的 Schema 示意如下；第一版支援的型別／巢狀深度／限制需依 Provider 能力與 Q-002／Q-003 核定，不宣稱任意 JSON Schema 均可原生生成：

```json
{
  "type": "object",
  "properties": {
    "summary": {"type": "string", "description": "根據 context 回答原始問題的摘要"},
    "steps": {"type": "array", "items": {"type": "string"}, "description": "可執行的處理步驟"}
  },
  "required": ["summary", "steps"],
  "additionalProperties": false
}
```

共用 §5.1.1 的 LLM Adapter／格式驗證邊界，每次呼叫提供各自 Schema；Prompt 控制內容，Schema 控制結構。Provider 支援時優先原生約束生成，回應仍由後端驗證，拒答／截斷／格式錯誤依核定政策處理。只改已知欄位名稱／包裝時，平台可確定性序列化，不需要再問一次 LLM；新增 summary／steps 等語意內容則在同一次 Generation 中產生並驗證。

**需要核定的邊界**：

- 使用者自訂的是回答業務內容；request_id、版本、usage／狀態及可信 citations 由平台管理，不讓自訂 Schema 改寫可信執行資訊。模型只能提出受控引用 ID，文件／Chunk／位置由 Engine 驗證與補齊。
- 既有 QueryResult.answer 與 07 的 HTTP 範例仍是字串基線。自訂物件的容器位置（例如 output 候選）、預設相容與版本遷移留 Q-002／Q-019，本輪不把字串 answer 靜默改成物件或直接替換整個 API 回應。
- 為接既有 UI／Evaluation，可指定主要回答文字欄位，例如 summary。路徑無效／非文字時須有可定位錯誤；沒有適用文字欄位的結構化結果，相關評估應明示不支援／略過政策，不能默默把整個 JSON 當答案字串。具體要求 Q-018。
- 第一版可先完整生成並驗證後回傳物件；若另支援 Streaming，部分 JSON／片段事件不視為已驗證最終結果，事件與錯誤契約由 Q-019 核定。
- 只調輸出 Schema／主要回答欄位屬 Inference Config 變更，需要重新測試／評估，不重建相容索引。停用時保留自訂草稿，不驗證／匯出其無效參數，不靜默丟棄使用者設定。

上述預設、控制項與 Schema 示意均為本次討論建議，UI 待辦見 10 UIB-009；Schema 型別通過不保證回答內容受資料支持。

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

### 7.1 開放範圍與共用契約

Module Developer 可針對各 Module 實作 Method；不再只把 Chunking／Rewrite／Rerank 視為可客製範圍。各 Module 的首批 SDK 介面與方法依 M0～M2／M6 逐步提供，未交付的介面不得宣稱已可擴充。Generation 的一般需求仍可先用 Prompt／內容設定，需替換演算法時走同一公開 Method 邊界。

同一 Module 的公開 I/O 與語意由平台維護，Method 必須相容；Method 自身 Config 可以不同。可使用契約明定的擴充欄位或具名稱／版本的能力宣告，不能自行增改必要頂層 key、把字典任意形狀視為相容，或要求下游默默猜測結構。公開契約可經版本化演進，並非永遠不能改。

ParsedDocument 的實際欄位／structure 尚待 [Q-002 子題](08_implementation_plan.md#parsed-document-schema-pending)；本輪沒有定案 blocks／page／Element 模型，也不新增直接匯入 Chunk／vectors 的入口。Inference 物件沿用 05 與 `inference-0.2-draft`，不得在開發指南另立第二套型別。

### 7.2 Method 必須宣告與配合的行為

| 項目 | 要求／規劃 |
|---|---|
| 身分與設定 | method_id、實作版本、模組類型；Config Schema 列明參數型別、預設值、必填／條件必填、限制與說明；與 package／SDK 版本分開追蹤 |
| I/O 與語意 | 宣告相容的 Module Input／Output 型別與 Contract 版本；驗證來源、ID、欄位繼承、分數方向與引用等不變條件，共用契約由平台維護 |
| 能力相依 | 宣告 requires／provides；包含 Parser 結構、索引能力、Tokenizer、向量維度／模型及配套 Method 相依；例如 Indexing 與 Retrieval 可讀寫的 artifact 版本 |
| 執行生命週期 | 宣告 async／batch／streaming 支援；依 Engine 規範初始化、執行、取消與釋放；具體簽名留 Q-002／Q-017 |
| 資源需求 | 列明外部 API／DB、Secret 邏輯引用、暫存／持久化儲存、CPU／Memory 的最低／建議需求與測量前提，以及 DEV 測試服務需求；透過受控 RunContext／服務解析介面取得資源，不把憑證寫入 Config、輸出或 Trace |
| 版本與變更影響 | 宣告相容的 SDK／Engine／Contract 版本；逐項說明實作升級或有效參數改變後，是否須重新 Parsing、Chunking、Embedding、重建 Index 或只重測 Inference；由 Engine 依相容政策判定，不只信任作者宣告 |
| 維護與驗收 | 提供維護者、用途／限制、範例 Config、輸入／預期輸出、固定測資、契約／語意測試、錯誤案例及相容版本測試 |

2026-10-28 配套核對補充：以上資源宣告描述方法需求，實際 API URL／Secret 綁定、儲存與 CPU／Memory 配額放在部署設定，不能混入跨環境共用的邏輯 Config。CPU／Memory 需求應註明資料規模、Batch／併發與測試條件；未量測時明示未知或估計，不能填示例數字冒充已驗證最低需求。首版不承諾自動由單方法需求計算整個 Runtime 的資源配額，彙整與部署驗證細節留 Q-021／Q-027。

DEV 服務宣告須區分「所需服務／能力」與「平台當前是否有核可測試服務可綁定」。有平台服務才可使用 DEV test use；沒有時明列需自行提供的設定，不能因宣告就假設平台供應。FTEST／ENT 由使用單位提供對應服務／Secret 綁定。需求內容可先以套件說明與驗收材料交付，機器可讀宣告的欄位／格式留 Q-002／Q-022。

變更影響需說明觸發條件與最早受影響階段；例如重新 Parsing 可能連帶重做後續 Chunking／Embedding／Indexing，不能把各階段視為互不相關的勾選。是否能重用中間結果、所需來源是否仍可取得，以及索引切換／回復政策依 Q-008～Q-010／Q-015，不預設平台一定保留所有中間資料。

共用邊界：Config 驗證 → Input Validation → 執行政策 → 自訂邏輯 → Output Validation → 來源／ACL／語意檢查。Pydantic 不取代「Rerank 只能選候選子集」等語意驗證。

### 7.3 成對擴充與 GraphRAG 邊界

Parser／Chunker 或 Indexing／Retrieval 可以由同一 Method package 成對交付，透過能力與 artifact 版本檢查相容性，不以 repo 名稱判斷。新增方法若仍遵循既有 I/O，就可接回既有 Pipeline。

GraphRAG 是擴充需求的例子，不是只註冊一個 Retrieval 就保證支援所有策略。若方法內部使用圖資料並回傳符合契約、可追溯的 Chunk 候選，可沿用既有下游；若需要實體／關係／社群摘要等新產物或跨模組新步驟，須先討論契約與流程擴充。不能將無對應來源的摘要偽裝成原始 Chunk。Method 內部可以使用自選框架，但跨模組邊界仍使用平台公開契約。

### 7.4 開發與發布邊界

第一階段依已確認的兩個 repo 分工，使用本機 IDE＋rag_engine 內的 SDK／Method 範本，在 methods 目錄開發並提交 PR；經契約／整合測試與審核後，由同一 repo 的 CI 建置包含 Engine、核可 Methods 與 Runtime API 的完整 Runtime Image。純方法變更不必修改 Engine 核心；共用 I/O／SDK／執行政策變更由 Engine Developer 審查，跨模組影響一起驗證。平台負責可用方法目錄、測試服務與執行結果，不先建瀏覽器程式編輯器、任意 Python 上傳或 Plugin Marketplace。正式發布權限、套件建置工具及隔離政策仍由 Q-022 核定。

Schema 驗證與 RunContext 介面不是程式隔離邊界；同程序 Python package 仍具有程序權限。若後續允許不受信任程式，須另定執行隔離、網路／Secret／資源限制。既有「共享 Runtime 不任意 exec 使用者程式」限制繼續適用。

### 7.5 Builder、助手與部署一致性

Builder 與 AI 助手使用目標 Engine／Runtime 實際支援且核可的方法目錄、Config Schema 與能力相依；不各自維護另一份方法清單。方法發布不等於所有 Runtime 已安裝，也不自動替換既有 System 的版本。使用者可看到不可用／不相容方法及原因，選擇必須通過相同 Engine Validator。

rag_platform 與 rag_engine 的服務邊界由 Runtime API／方法目錄承接，接口細節見 07。若 API／Config Schema 相容且既有表單可呈現，新 Method 經 Runtime 更新即可提供 Builder 選用；若修改了不相容接口或需要新增 UI 控制項，仍需協調 Builder 更新。套件集中於同 repo 不代表任何 Runtime 改動都免重新部署；採用新版的方法／Engine 必須經相容測試並部署該 Runtime Image。

基本設定可依 Config Schema 產生表單，跨模組連動仍需能力規則與顯示資訊；不能承諾任何自訂 UI 都只靠 JSON Schema 自動產生。實際表單／版本呈現列於 [10 UIB-010](10_ui_adjustment_backlog.md#uib-010-method-catalog)，本輪不修改 Prototype。

DEV 與 FTEST／ENT 維持相同方法選擇／解析版本與邏輯 Config，環境服務綁定分開；交付需驗證目標 Image 包含所需方法與相依套件。僅匯出 YAML 不會自動交付 Method 程式。更新 Method 後重測／重建的判斷依 Q-015，不以版本號單獨認定索引相容。

開發者實作步驟、Python 介面示意與交付檢查見 [11](11_method_developer_guide.md)；決策狀態以 [08 Q-022](08_implementation_plan.md#q-022) 為準。

### 7.6 設定描述與動態表單（D-42）

2026-10-28 已確認依 Schema／UI hints／相依規則規劃 Method 設定。具體描述與驗收案例集中於 [12](12_method_schema_ui_contract.md)，不在本文件另建第二套欄位定義；`method-ui-0.1-draft` 尚未凍結為正式 SDK／HTTP 契約。

- Method 宣告 `config_type`，共用父類別提供 Schema 輸出，Registry 強制檢查；不要求每個 Method 重寫產生 Schema 的 abstract method。UI hints 可使用預設值，特殊控制項明確宣告必要功能。
- Config Schema、動態選項／能力與跨欄位規則共同參與 Engine 驗證，UI／AI／Python／HTTP 不能各自維護不同的有效性規則。Config Schema 與 Module I/O Contract 分開，ParsedDocument 待決狀態不變。
- 取得方法描述不應初始化模型或外部服務；候選欄位／LLM／索引能力由 Engine 的版本化 Context 解析。目錄可用不代表真實連線／資料就緒已驗證。
- 區分「不適用所以排除有效值」與「已選設定不合法所以阻擋」；UI 停用／收合不等於 Engine 可以略過必要驗證。相依失效保留原選擇，不自動換 Method 或搜尋路徑。

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
- 在乾淨環境以 rag_engine 的 Method package 建置產物驗證安裝、註冊、設定、單方法與完整流程，避免靠原始碼路徑或私有匯入才能執行；不要求另建 repo，也不能靠修改 Engine 核心或 Builder 原始碼才加入每個普通 Method。
- 重複識別、缺失套件、不相容版本／結構／artifact、違反語意的輸出均可定位失敗；Image／方法版本可追溯，升級不默默改變既有 System。
- 尚未核定能力回報不支援，不以 Mock 或靜默 fallback 代表完成。

開發階段與驗收資料見 [08](08_implementation_plan.md)。
