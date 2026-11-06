# Engine 執行、Module 能力與 Component 開發

## 閱讀目錄

- [目標與依賴邊界](#src-04-1-目標與依賴邊界)
- [Engine 入口與初始化（建議，Q-002／Q-017）](#src-04-2-engine-入口與初始化建議q-002q-017)
- [共用執行政策](#src-04-3-共用執行政策)
- [Ingestion 模組](#src-04-4-ingestion-模組)
- [Inference 模組](#src-04-5-inference-模組)
- [Evaluation 邏輯](#src-04-6-evaluation-邏輯)
- [客製化與擴充](#src-04-7-客製化與擴充)
- [Engine 完成條件](#src-04-9-engine-完成條件)
- [SDK 執行物件、Context 與內部錯誤草案](#src-05-5-共用執行與錯誤物件)
- [Developer：開發模式與 repo 分工](#src-11-2-開發模式與-repo-分工)
- [Developer：識別、版本與相依能力](#src-11-3-識別版本與相依能力)
- [Developer：Python Component 介面示意](#src-11-4-python-component-介面示意)
- [Developer：安裝、import 與 Registry](#src-11-5-安裝import-與-registry)
- [Developer：測試與審查](#src-11-6-測試與審查)
- [Developer：從開發到 Builder 與部署](#src-11-7-從開發到-builder-與部署)
- [Developer：待決項與開始時機](#src-11-8-待決項與開始時機)
- [Parser 教學：共用 Pydantic Contract：先給一版具體型別](#src-16-2-共用-pydantic-contract先給一版具體型別)
- [Parser 教學：Local Developer：實作 Parser ABC](#src-16-3-local-developer實作-parser-abc)
- [Parser 教學：Remote Developer：實作 API，不需要 Component ABC](#src-16-4-remote-developer實作-api不需要-component-abc)
- [Parser 教學：Developer 最少要拿到什麼？](#src-16-5-developer-最少要拿到什麼)
- [Parser 教學：如何重現](#src-16-6-如何重現)
- [C：Remote Manifest 的內容與註冊流程](#src-18-3-service-manifest-與註冊流程)
- [Remote 的邏輯參數、啟動設定與環境綁定](#src-18-4-三類設定與固定服務)
- [描述與開發完成條件](#描述與開發完成條件)

- [候選程式目錄與建置邊界](#repository-layout)

- [Remote 推論公開邊界](#remote-inference-boundary)

- [SDK 如何提供設定描述](#sdk-schema-description)


更新：2026-11-05。本手冊主責共用 Flow、執行政策、Module 方法、SDK／Registry 與 Developer 流程。資料形狀引用資料契約；Descriptor 候選、HTTP 與 UI 各有自己的主責手冊。

<a id="src-04-1-目標與依賴邊界"></a>
## 目標與依賴邊界

**開發者提供 Config 及必要服務，即可直接執行 Ingestion／Inference；不需要 Builder UI、Builder DB 或 HTTP。**Engine 負責模組組裝，07 只呼叫此能力並包裝 API／工作狀態。

Ingestion：Import → Parsing → Chunking → Embedding → Indexing。
Inference 基線：Query Transformation → Retrieval／Fusion → Rerank → 最終檢索結果。目標需可設定融合策略與合併時點；Engine 依核定 Fusion Plan 保留逐路結果與組合 Fusion／Rerank，見 相關章節。
Evaluation：重用相同檢索入口的評估邏輯，任務排程與報告儲存由 Runtime API／部署手冊 負責。

- 固定 Pipeline，不要求使用者建 DAG。
- Config、業務 Payload、可信 RunContext 分開；資料結構見 [資料契約](02_data_contracts.md)。
- LangChain 物件只在 Adapter 內轉換，不作持久化／跨模組 Contract。
- 不同框架／自訂 Function 或 Class 透過相同 Contract 包裝。
- 純全文可跳過 Embedding；None 模組回傳相同語意的 pass-through 結果。

<a id="src-04-11-sdkengine-與-component-package"></a>
### SDK、Engine 與 Component package

| 元件 | 職責 | 依賴邊界 |
|---|---|---|
| `rag-engine-sdk`（暫名） | 共用 I/O 型別、各 Module 的公開介面、Config 驗證與受控 RunContext；另規劃契約測試工具 | 不依賴 Engine 私有實作或 Builder；資料總覽見 05，IngestionDocument／ParsedDocument／Chunk 精確定義見 資料契約手冊 |
| `rag-engine`（暫名） | Registry、相容性驗證、Pipeline 組裝、生命週期、執行政策與資源管理 | 使用 SDK 契約，載入已安裝且核可的 Component package |
| rag_engine 內的 Component package | 實作一個或多個 Module 的 Component，附設定、能力宣告、測試與說明 | 依賴 SDK 公開介面及自身必要套件；不依賴 Builder 或 Engine 私有類別 |

內建與開發者提供的 Component 應遵循相同公開契約與語意檢查，不能以內建方法的私有捷徑作為唯一可行用法。2026-10-28 已確認：SDK、Engine、本地 Components／Remote Adapters 與 Runtime API 同放 `rag_engine` repo，Builder 前後端放 `rag_platform`，見 [架構與責任](01_architecture.md#src-03-31-系統組成與管理階層)。Module Developer 在 components 目錄提交 PR，不要求另建 Component repo；同一 package 可包含成對的 Indexing／Retrieval。套件邊界仍保留，精確名稱／目錄由 Q-001 核定。

SDK 的「獨立」是可安裝、可依賴的公開邊界；不表示 Component 的完整 Engine 整合測試不需要 Engine。單一 Component 測試可用 SDK 測試工具與資源替身，整合測試使用同一交付版本中的相容 Engine。Engine 與 Component packages 共同納入完整 Runtime Image；不以拆出另一個 Components 服務作為首期執行模型。

<a id="src-04-2-engine-入口與初始化建議q-002q-017"></a>
## Engine 入口與初始化（建議，Q-002／Q-017）

<a id="src-04-21-python-介面草案"></a>
### Python 介面草案

```python
# 目標用法示意；目前尚未存在這些類別，命名待 Q-002 核定。
engine = RetrievalEngineLibrary(
    registry=registry,
    component_resolver=components,
    resource_manager=resources,
)
snapshot = await engine.prepare(
    load_config("retrieval.yaml"),
    deployment_settings=deployment_settings,
)
try:
    result = await engine.ingest(
        ingestion_input, config=snapshot, context=trusted_context
    )
    retrieval_result = await engine.query(
        query_input, config=snapshot, context=trusted_context
    )
finally:
    await engine.aclose()
```

D-62 已確認 B：共用 Flow／Executor，每次執行傳入已驗證 Config 快照，並依 Module 解析 Component。上述 prepare／Resolver／ResourceManager 命名及簽名仍是草案，不是新增已發布 SDK。Memory 模式不要求遠端 DB；Config 定義邏輯，Context 提供正確 System 的資源／Binding。同一 Config 可搭配不同環境綁定。此例為獨立 Python 程式，結束時才關閉 Engine；共用 API service 不在每次請求後關閉共用資源。直接 SDK 不回 HTTP code，07 將領域錯誤映射為 HTTP／Job 回應。

<a id="src-04-22-編譯與初始化流程"></a>
### 編譯與初始化流程

D-61／D-62：下列流程準備一份 System Config 的有效快照及必要資源，不要求為其建立專屬 Flow。Builder 共用 API service／Executor，請求開始時由可信路由選定配置；FTEST／ENT 啟動載入單份配置，執行仍使用同一 Executor，見 [架構與責任：模式對照](01_architecture.md#src-03-31-系統組成與管理階層)。

1. 讀取 YAML／JSON，驗證 Contract 版本及未知欄位；安全解析，不執行設定內的程式碼。
2. 將 UI Draft 編譯成 Effective Config，排除未啟用方法／服務草稿。
3. 根據 Registry 驗證 I/O、方法能力、欄位來源、Profile、模板與可過濾能力。
4. 依部署設定解析 Config 中的服務邏輯引用與 Secret；以受授權的 Workspace／System／集合建立 Binding，不把環境 URL 或目標集合混成模組邏輯。
5. 初始化被使用的 Client／Tokenizer／Parser／Index Adapter；不載入未使用服務。
6. 若有既存資料／Manifest，檢查相容性；MongoDB 模式按相容版本重建 Local Search。
7. 回報配置／資源準備結果及索引就緒狀態；失敗釋放本次新建且未被其他工作持有的資源，不誤關其他 System 正在共用的資源，也不宣稱失敗配置已可查詢。

Schema 格式檢查、真實連線檢查、Profile 相容檢查、索引可查詢是不同狀態。Runtime 可啟動且接受 Ingestion，不代表 Query 已可用。

<a id="shared-flow-execution"></a>

<a id="src-04-221-共用-flow-與逐次設定d-62-已確認方向"></a>
### 共用 Flow 與逐次設定（D-62 已確認方向）

Flow 只保留既定 Module 骨架與已核可的分支／合併規則。Config 儲存或啟用時先驗證 I/O、版本、相依及 Remote 覆蓋範圍，可快取解析後步驟；不要求每次請求重做完整 Schema 驗證，也不新增任意 DAG。

以下以本地 Ingestion 的 ModuleResult.data 為例，不凍結 SDK 方法、Config 格式或包裝。Inference 直接傳 QueryContext[]，不套用此處的 data 解包：

```python
async def execute_ingestion(data, snapshot, context):
    # snapshot.steps 是內部解析結果，不是新增公開 Config／資料欄位。
    for step in snapshot.steps:
        component = await component_resolver.resolve(step, context)
        result = await component.run(
            data, config=step.config, context=context
        )
        data = result.data
    return data
```

- 每次請求與已接受的 Ingestion 文件固定 Config 快照，不在 Module 邊界重新選最新版本；D-63：該 System 有 queued／running Ingestion 時不啟用新版，工作結束後才允許套用；既有工作不重綁新 Config。舊資源回收與未知 Remote 寫入仍待 Q-017／API-D05。
- 共用 Flow、Component 實例及模型／Client／索引資源是不同層次。無狀態且可安全併行的實例可共用；有狀態或特定資源綁定的實例可分開管理，確切快取／回收介面待 Q-002／Q-020。
- 可共用實例不得把本次 input／config／output 放進跨請求可變 self；必要工作資料放區域變數，資源由正確的可信 Context／Resolver 取得。不得將 System A 的 IndexBinding 或資料誤用於 B。
- Remote 整段接管在解析計畫中只保留一次呼叫，跳過已涵蓋 Modules；B 不要求遠端服務也使用同一套本地 run 簽名，不將整份 System Config／Context／Secret 自動轉送。
- 純參數變更與模型／索引語意變更分開；B 不免除資源重新準備、索引相容檢查或重新 Ingestion，也不承諾零停機。

<a id="src-04-23-registryfactory"></a>
### Registry／Factory

建議每個註冊 Component 提供 module_type、component_id、implementation_version、input_schema、output_schema、config_schema、requires、provides、supports 及 factory。由 Engine 編譯器串接，不由 Builder 寫另一套組裝流程。

依 [D-43 命名對照](01_architecture.md#component-terminology-migration)，擴充單位統一使用 Component／component_id。早期 Registry 草案曾以 module_id、後以 method_id 表示具體實作；目前 module_type 表示職責，例如 chunking，component_id 表示具體元件，例如 team_a.chunking.custom，Python class 名稱只是實作符號。同一 Component 可在執行時接收不同參數，不需要因此新增 component_id 或必然建立新實例；有狀態／特定資源需求時仍可建立多個 Component Instance，node_ref 另辨識配置位置。正式 Config 結構、舊別名與遷移仍由 Q-002 核定，本輪沒有修改 Prototype／公開 I/O Schema。

```yaml
component_id: company.chunking.recursive
module_type: chunking
implementation_version: 1.0.0
contract_version: 0.1-draft
requires: [document.string_field, tokenizer]
provides: [chunk.fields, chunk.metadata._rag.source_refs]
supports: {async: true, batch: true, streaming: false}
```

宣告能力須有契約測試。Registry 須可追溯 distribution package 名稱／版本、Component 實作版本、SDK／Engine 相容範圍與 Contract 版本。`component_id + implementation_version` 在同一有效 Registry 內不能對應兩份不同實作；重複註冊應明確失敗，不能由載入先後決定覆蓋。

<a id="src-04-25-remote-service-註冊與整段執行"></a>
### Remote Service 註冊與整段執行

Local 仍依 相關章節～2.4 載入 package；Remote 實作可保留在 Developer 私有服務，透過核可 Manifest／環境綁定及 Runtime 已支援的共用 Adapter 接入，不要求將遠端演算法安裝進 Runtime。目錄須分清 Local 實作與已註冊 Remote 能力，不能只以 Image 內的 Python 類別清單判斷服務可用性。

Remote Pipeline 宣告同一 Pipeline 中連續範圍、邊界 Contract 與 requires／provides；有效計畫僅保留一次遠端節點，跳過接管的本地步驟，拒絕重疊或不相容接線。例：IngestionDocument → 遠端 Parsing／Chunking／Embedding → Chunk[] → 本地 Indexing。輸出仍須符合原有 metadata／來源／向量語意，不要求傳中間 ParsedDocument。涵蓋 Indexing 時需相容的 Retrieval 與可信索引綁定；精確返回／傳參協定尚待核定，不能據此假定任意成對服務都相容。

API 只傳可序列化且已核定的業務資料及明確支援的參數，不傳完整 RunContext；第一版不傳 data_space_id。計畫驗證、呼叫錯誤／版本與整段 Trace 由 Engine／Adapter 處理，部署則由 Runtime API／部署手冊 管理。詳細邊界、固定服務及驗收見 [Engine／Component 開發](#src-11-2-開發模式與-repo-分工)。

<a id="src-04-26-kiss選填追溯與-metadata-提示d-52"></a>
### KISS：選填追溯與 metadata 提示（D-52）

Component 只需滿足共用 I/O 及自身功能語意，不強制實作 _rag；有提供標準追溯時才驗證。metadata 可攜帶 Component 明確支援的文件層提示；例如 Chunker 讀 chunking_mode 決定 split／passthrough，缺省 split，不需另設通用規則引擎。不支援提示的 Component 不會自動獲得該邏輯。Config、業務提示及可信 Context 仍分開，授權／Secret 不由 metadata 控制。詳見 [Chunk](02_data_contracts.md#src-15-1-共用物件)。

<a id="src-04-3-共用執行政策"></a>
## 共用執行政策

<a id="src-04-31-io-接線"></a>
### I/O 接線

Ingestion 本地教學可用 ModuleResult[T] 包裝成功資料；推論三模組的業務接線統一 list[QueryContext] → list[QueryContext]，沒有 InferenceState／data 外框。D-62：本次 Component Config 以獨立參數傳入，資源與可信授權由 context 提供；兩者不混同。正式生命週期與錯誤介面仍待 SDK 核定。

| 模組 | 業務 Input | 業務 Output | 另行注入／保留 |
|---|---|---|---|
| Import | IngestionDocument：content／base64／uri 三選一 | 通過共同外層驗證的相同 IngestionDocument | 來源授權、共用內容取得；Builder／呼叫端處理上傳轉換 |
| Parsing | 與 API 共用 Schema 的 IngestionDocument | ParsedDocument 清單 | SDK resolver／可信 Context、依能力自動路由、必要 profile |
| Chunking | ParsedDocument 清單 | Chunk 清單，vectors={} | Tokenizer、必須繼承資訊 |
| Embedding | Chunk 清單 | 相同成功 Chunk＋vectors | Profile、逐項錯誤；不回獨立 VectorSet |
| Indexing | 帶向量或純文字的 Chunk 清單 | IndexBinding、逐項結果；就緒狀態獨立由 Runtime 管理 | 授權目標／刪除事件；提交政策待決 |
| Query Transformation | QueryContext[] | 原始／衍生 QueryContext[]；保留 ori_query、複製 filters／metadata | llm_ref、Prompt；共同 Schema 見 [資料契約](02_data_contracts.md#src-05-46-querycontextresultsetresultitem已確認的簡化-contract) |
| Retrieval | QueryContext[] | QueryContext[]，填入各 context 的 key／items 清單 | IndexBinding、Query Encoding、可信 ACL 由 Context 提供；按 Config 融合 |
| Rerank | QueryContext[] | 同型別；覆寫目前 score、排序／Top N；None 沿用 | 模型服務、Query 來源與 Chunk.fields；不保留歷史清單 |
| Evaluation | Dataset、Target | 逐題結果與指標摘要 | 版本綁定、Judge；工作儲存由 Runtime API／部署手冊 提供 |

原始問題不被 Rewrite 覆蓋。新版不預設公開對話歷史；歷史若啟用需另訂契約，不因舊草案有 history 欄位就宣告已支援。

原始問題是 Inference 的持續傳遞資料：Query Transformation → Retrieval／Fusion → Rerank（含 None）→ 最終檢索結果都必須保留，不能只在第一步或 HTTP 層暫存後丟失。`include_original` 只控制是否把原始問題加入搜尋 Query 清單，不影響 Rerank／檢索結果消費端 仍取得原始問題。逐 Query 的 Rerank 若改用衍生 Query，需依 Q-014 的計畫顯式定義。

<a id="src-04-32-錯誤重試與觀測"></a>
### 錯誤、重試與觀測

- 結果必須能對應輸入的成功／失敗／skipped 項目。空檢索為成功，索引或 Provider 故障為失敗。
- D-56 已確認以 document_id 完整替換、逐文件成功／失敗；未完整成功不得標 completed，失敗清理／保留舊版由 backend 落實。D-60 不加平台 Query 讀寫鎖，允許更新中讀到暫時新舊混合，不保證原子可見性。Run partial 彙總方向已確認，精確 Envelope 及實體提交機制仍待整理，見 [Runtime API／部署](06_runtime_api_and_deployment.md)。
- 重試由共用政策管理；HTTP 重送與內部重試不能形成無界倍增。僅在可安全重試且暫時性錯誤時啟用。
- Indexing／資產提交具副作用，未知寫入不自動重試；具體冪等／版本控制待 Q-008／Q-017。第一版不保存續跑 checkpoint，不以讀取成功宣稱提交已完成。
- 每個本地模組／單 Module 遠端呼叫記錄 System／Config／Run／Trace、耗時、數量及標準錯誤；Remote Pipeline 預設以整段呼叫記錄，內部各步診斷為選配。不記錄真實 Secret，未知用量不填 0。
- Provider failure 不偽裝成沒有相關資料；fallback 需明示 warnings 及實際方法。

D-56 已確認不做斷點續跑、Runtime 重啟不恢復工作／記憶體狀態，並由 Runtime 統一 Queue／Inference 流量控制；不將工作狀態塞進共用 I/O。Timeout、重試預算、取消、索引發布實作與 fallback 仍待 Q-009／Q-017／Q-023；Remote 寫入結果不明不能當作無副作用。

<a id="src-04-4-ingestion-模組"></a>
## Ingestion 模組

<a id="src-04-41-import"></a>
### Import

**目的與邊界**：Engine 接收扁平 JSON，驗證共用 IngestionDocument，並提供共同的內容取得能力；文件／CSV 上傳轉換由 Builder 或呼叫端處理，不提供 Engine multipart，不做 PDF／OCR 語意解析或 Embedding。

**Config／I/O**：[資料契約](02_data_contracts.md) 記錄 API／Parser 共用的 IngestionDocument 與 [同一份 JSON Schema](../schemas/ingestion_document.schema.json)。content／base64／uri 三選一，文件 ID、版本與 metadata 持續傳遞；SDK resolver 共用 URI 取得與 Base64 解碼，不另建 ParserInput envelope。D-58 的 Runtime body 為非空 IngestionDocument[]，每份 item 與 Parser input 相同；D-64 已確認的 Runtime body／來源大小與文件 Deadline 初始預設集中見 [Runtime API／部署](06_runtime_api_and_deployment.md)；原始資源保存與逐模型／Client timeout 仍另行核定。

**驗收方向**：相同內容經 inline／Base64／URI 後，在相容格式下具有相同解析語意；Builder CSV 映射一次後與直接 JSON 得到一致結果；不丟失身分／metadata，不接受未授權來源。外層多重來源、格式／內容不符及超限須明確失敗。

**待決**：Q-002、Q-005、Q-007、Q-008、Q-016、Q-017、Q-019。

<a id="src-04-42-parsing"></a>
### Parsing

**目的與邊界**：相容 Parser／Adapter 解析原始內容或正規化已解析資料，產出四鍵 ParsedDocument：document_id、source_revision、units、metadata。units 是平面的 list[dict]，每筆直接放 text 與其他欄位，不包 fields、不要求 unit_id。Parser 負責文件結構、語意單位與閱讀順序；不生成向量或自動摘要。

**輸入與路由**：與 API 共用 IngestionDocument（content／base64／uri 三選一）；由 Component 支援的格式與 profile 派送，歧義需明確解決。Builder CSV 每列先映射一份 IngestionDocument，再組成 Runtime List body，Parser 逐文件正規化，不要求重複設定相同欄位映射。

**輸出與驗證**：以 [資料契約](02_data_contracts.md)／[Schema](../schemas/parsed_document.schema.json) 驗證。text-spans／page-blocks 等上游結構由 Parser 內部處理，不再作 Chunker 的輸入分類。表格整理成逐列語意文字或 Markdown；圖片需具備 OCR／描述能力。Header-aware 需要 Unit 文字保留 Markdown 標題。來源欄位可附 page／slide／sheet 等；不得捏造位置或把無內容當成功。

**供應者相容性**：Docling／MinerU／MarkItDown／PyMuPDF4LLM 的新版映射方向與驗證限制見 [ParsedDocument](02_data_contracts.md#src-14-5-parser-相容性與驗證範圍)。舊結構契約的通過報告不當成 units 新契約驗收；正式 Component 及解析品質需另驗證。

**待決**：Q-002、Q-005、Q-006、Q-007；新格式能力同步 Registry／UI，原型變更先記 UIB-011／012。

<a id="src-04-43-chunking"></a>
### Chunking

**Output 草案（2026-10-30，D-47）**：[資料契約](02_data_contracts.md) 與 [Chunk Schema](../schemas/chunk.schema.json) 是六鍵輸出的共用定義。Chunker 輸出六鍵，vectors={}；_rag／source_refs／fingerprint／ordinal 由 Component 選擇是否提供，不能因缺少追溯拒收。多欄位 2＋3 得 5 個 Chunk；選用參考 ID／序號 helper 時才依其穩定順序規則驗證。參考測試只驗已提供的切片／資料，不代替真實 Chunker 演算法與 Tokenizer 驗收。UI 待辦 UIB-013。

**資料／能力補充（2026-11-02）**：Input 引用 [ParsedDocument 0.2 Schema](../schemas/parsed_document.schema.json)。每個任務選一個 Chunker，逐一處理所有 Units，不跨 Unit 合併或 overlap；移除依 structure 類型選 Chunker 的 Router。進階多欄位任務各自輸出後串接，不交叉配對。欄位／Markdown 格式／Tokenizer 能力仍需檢查，UI 遷移見 UIB-014。

**目的與方法**：Fixed-size／Recursive／Header-aware；預設直接切 units[i].text 並寫回 text，不顯示欄位選單、不自動複製其他 fields。進階才設定有序任務，每個任務一個 split_field／output_field＋明確 copy 映射；同來源可切分且完整複製，但輸出名稱不能衝突。metadata 預設全部繼承，不再逐欄勾選。三種方法均以 Token 計量，沿用指定 Tokenizer／revision。2026-10-16 新增的「fix chunk」統一稱 **Fixed-size Chunking（固定 Token 視窗）**；方法已列入需求；Prototype v0.10 有設定展示，正式 Engine／Tokenizer 尚未實作。

| 方法 | 切分依據 | 有效設定 |
|---|---|---|
| Fixed-size | 按固定 Token 視窗前進，不依句子、分隔符或標題找邊界 | size、overlap、tokenizer；共用 split／copy，metadata 預設全部繼承 |
| Recursive | 依分隔符優先序找邊界，過長片段繼續細切 | 共用設定＋separators、keep_separator |
| Header-aware | 先依標題層級切分，超長章節再用 Recursive | 共用設定＋header_levels、標題能力及 Recursive 備援參數 |

Fixed-size 的邏輯步長為 `size - overlap`；從 Token 0 開始，最後一塊不足 size 時保留、不補齊。視窗涵蓋文件結尾即停止，不再產生只重複末尾 overlap 的多餘 Chunk。例如 Token 串長 11、size=4、overlap=1，半開區間依序為 `[0:4]`、`[3:7]`、`[6:10]`、`[9:11]`；長度為 10 時則在 `[6:10]` 結束。這是 Token 視窗語意例子；Unicode 完整邊界、offset 映射及實際模型輸入重新計數的精確策略仍由 Q-004 核定，不能靠任意 decode Token 片段破壞原文。

**處理**：

1. 檢查必要切分欄位存在、為非空白 string，且明確 copy 欄位可取得；缺失／型別錯誤／全空白不視為成功，必要任務零產出須明確失敗。可選複製第一版不先擴充（D-48）。
2. 依所選方法切分：Fixed-size 使用上述固定視窗；Recursive 依 separators 優先序切分，必要時處理過長片段，size 是上限、overlap 是目標值。
3. Header-aware 先依可靠標題層級切分，再對超長章節 Recursive；標題取自當筆 Markdown；無標題時依 Component 明確策略處理，不跨 Unit 尋找。
4. 記錄 unit_index 與原 Unit 字串範圍，不從帶 overlap 的文字猜測位置，不跨 Unit 合併。
5. 從同一 Unit 複製指定欄位到 Chunk.fields；文件摘要保持文件摘要。繼承 ParsedDocument 中經 Schema 驗證的全部業務 metadata，並保留必要可信來源／ACL；Component 可選擇提供 metadata._rag.source_refs／chunking，輸入不能覆蓋平台保留資訊，完整可信區協定見 Q-006。第一版不新增 metadata 排除表單，有明確需求再規劃。
6. 由 Component 或 SDK helper 產生必要且唯一的 chunk_id，初始化 vectors={}。fingerprint／ordinal 的 Hash 規則僅為選用參考工具，不強制所有 Component 實作或輸出，見 [資料契約](02_data_contracts.md#src-15-5-有效切分設定與-fingerprint選用參考工具)～6。

**驗證／例外**：size 為正整數、overlap 為整數且 `0 ≤ overlap < size`、Tokenizer 可用；涵蓋重複文字、非 BMP 字元、空段及極長無分隔文字。Fixed-size 不啟用 separators／keep_separator／header_levels，也不要求 結構化 heading Blocks；未啟用的方法參數可保留草稿，但不驗證或匯出為有效參數。複製欄位未被主要內容切分，不保證其長度小於 size。

**驗收**：單塊不超過約定 Token 上限；offset 可精確還原主要文字；相同輸入與切分設定得到相同 ID；Header-aware 標題能力不足會拒絕。Fixed-size 另驗證零 overlap、短文件、恰好整塊、末塊不足、Unicode、切到結尾不再輸出 overlap-only Chunk，且不因變更停用的 separators／標題層級而改變結果。切換方法、size／overlap 或有效 Tokenizer 屬 Ingestion 配置變更，需重新切分及重建受影響索引。

**待決**：Q-004、Q-005、Q-007；Token 精確計數、切分 fallback 與 overlap 邊界需測試材料。

D-53 真實 Engine 功能待實作，Prototype v0.12 已有控制與教學預覽：預設 Chunker 可選擇另留每 Unit／任務的完整原文 Chunk，預設關閉；已有相同完整切片則不重複新增。它與 copy 原文欄位獨立，不跨 Unit 合併，新增結果仍走 Embedding／Indexing 與模型上限檢查。行為與例子見 [Chunk](02_data_contracts.md#src-15-1-共用物件)。

<a id="src-04-44-embedding"></a>
### Embedding

**目的**：選 fields 內容，依 mappings 將 Dense 向量寫入 vectors。多個 output_name 與來源明確對應；與 Indexing 分離。

**處理**：

1. 預設 Embedding Component 可選擇先以模板組合 fields 與固定文字，寫入獨立衍生欄位（預設 embedding_text），再依映射解析 Profile／服務／Tokenizer 與 document encoding；來源欄位記入向量 source_field。不啟用時沿用原路徑，詳見 [資料契約](02_data_contracts.md#src-15-91-embedding-前的欄位模板組合)。
2. 對實際來源內容檢查 Token 極限，含前綴及特殊 Token；不能只驗 Chunk Size。
3. 按 Batch Size 呼叫 Embedding Adapter；現有 Prototype 的格式基線為 OpenAI-compatible embeddings。正式首組服務、相容範圍及模型契約仍待 Q-003，不把原型格式當作所有 Embedding API 的通用標準。
4. 驗證回應 index 對應、數量、維度與有限值；不能因回傳順序錯誤把向量寫給其他 Chunk。
5. normalization 與 metric 依 Profile 執行；記錄模型／版本／Provider request ID。
6. 寫回原 Chunk.vectors 的命名物件（values、embedding_profile_id、source_field），精確格式引用 Chunk手冊／共用 Chunk Schema；保留 fields／metadata。預設 fields.text → vectors.text，其他映射由進階設定；純全文 Pipeline 不初始化此服務。

**例外**：缺欄位、超長、429／Timeout、批次缺項、維度錯誤與非法數值。截斷或 partial 需明確政策，不能默默處理。

**驗收**：一筆 Chunk 可有兩個具名向量；後續仍取得原文；Query Encoding 依相同 Profile 配對；換模型／維度被判需重建。

**待決**：Q-003、Q-004、Q-009、Q-017。Sparse、多模態及 late interaction 為後續。

<a id="src-04-45-indexing-與搜尋-adapter"></a>
### Indexing 與搜尋 Adapter

**目的**：保存 Chunk，依欄位用途建索引，回報寫入與可搜尋狀態。Engine 在初始化時透過 Adapter 準備授權範圍內的目標；不依賴 Builder 才能 provision。

**2026-10-16 已確認的簡化**：預設保存 Chunk 的全部 fields／metadata，不再要求使用者填 stored_fields 或勾「儲存內容」。保存內容與建立搜尋索引分開：使用者只選全文欄位、向量欄位與可過濾欄位；未選搜尋索引的 title 等欄位仍可供 Rerank／檢索結果消費端／引用使用。保留 metadata 不代表自動對所有 metadata 建立 Filter／全文索引。向量保存與恢復沿用既有完整 Chunk／vectors 政策，不因拿掉內容選單而刪除 vectors。

**處理**：

1. 驗證完整 Chunk 與 fulltext／vector／filter 選擇及 Profile；全部 fields／metadata 保存，ID／版本／來源／ACL 固定保留，不再以使用者的保存投影刪欄位。
2. 比較目標 Schema／Profile，拒絕不相容寫入，避免不同模型混在同一向量欄位。
3. 依版本／冪等策略寫入 Chunk，維護 chunk_id 對照及 Binding。
4. 按後端 refresh／發布規則回報 searchable；write_acknowledged 不等於 searchable。
5. D-56：同 System／document_id 成功後整份替換並清除不再產出的舊 Chunk，失敗保留最後成功版本；實體提交與崩潰可見性需 Q-008／Q-009 驗證，D-58 文件管理需要存在／ID 清單與 retire 直接刪除，精確介面見 Runtime API／部署手冊／IndexBinding手冊。

| Adapter | 內部責任 |
|---|---|
| ES | 組合 Mapping；全文 text、精確 keyword、Dense vector；全部內容可取回但只替選定欄位建立對應搜尋能力；相容查詢及 refresh |
| Local Search | 每個具名向量管理 FAISS index；每個全文欄位管理 BM25；向量 ID → chunk_id；完整 Chunk 共用一份 |
| Local／MongoDB | 保存 Chunk／vectors／Profile Manifest；重啟按相容版本重建搜尋結構，不重新 Parsing／Embedding |

FAISS 的維度／metric 不足以證明向量空間相容。cosine／inner product／L2 的 normalization 與對外 relevance 轉換必須定義；中文 BM25 需斷詞方案。不能把 post-filter 與 Top-K 前授權過濾視為等價。

**驗收**：ES 與 Local 共用契約測試；未建搜尋索引的 fields／metadata 仍完整可取回；metadata 不因未勾可過濾而遺失；只有宣告的欄位可搜尋／過濾；不出現跨 System Chunk；寫入失敗／不就緒不回可查詢；Memory 重啟清空、MongoDB 可驗證恢復。

**待決**：Q-008～Q-013、Q-015；ES 版本／授權 Q-001。

<a id="src-04-5-inference-模組"></a>
## Inference 模組

<a id="src-04-51-query-transformation"></a>
### Query Transformation

**方法**：None／Rewrite／Multi-query；原始問題永遠保留。count 指衍生 Query 數，不含選配原始問題。

**處理**：None 回一筆原始 Query；Rewrite 使用 {{query}} 產生一筆；Multi-query 使用 {{query}}／{{count}} 產生多筆。include_original 由程式處理，不交由 Prompt 決定。引用 System 共用 llm_ref。

**驗證**：非空問題、合法模板、LLM 引用、衍生結果數量／文字合法。去除相同問題、模型輸出格式不符及降級政策由 Q-003／Q-023 核定；不自動忽略壞結果。

**驗收**：Rewrite 不覆蓋 original_question；Multi-query count 與原始問題選項獨立；None 不呼叫 LLM；Rerank／檢索結果消費端 始終取得原始問題。

<a id="src-04-511-討論提案rewrite-的結構化輸出與共用-llm-邊界"></a>
### 討論提案：Rewrite 的結構化輸出與共用 LLM 邊界

**狀態：2026-10-16 提案，待使用者確認及 Q-003／Q-017／Q-023 核定；不是已實作或已凍結的公共 Contract。** 建議 UI 加單模組試跑，見 Builder UI／Backlog手冊／UI Backlog手冊；輸出形狀與數量由平台提供，Prompt 主要描述如何改寫，不讓使用者每次重寫機器可讀契約。

建議 Rewrite 與 Multi-query 共用 `{queries: [...]}` 的結果形狀；Rewrite 目標為 1 筆，Multi-query 目標為 Config.count 筆。原始問題及 include_original 由平台處理，與模型要求生成的數量分開。ori_query、filters、metadata 由 Runtime 保留／複製，LLM 只生成 query 文字，不負責授權或結果物件。

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

服務連線與模型引用集中管理，Schema 由每次模組呼叫傳入，不在同一 LLM 服務上固定一種輸出格式。使用 LangChain 時可採其 Model structured-output 介面，不需要為單次 Rewrite 引入完整 Agent。

官方依據（查核 2026-10-16）：[JSON Schema 的陣列長度限制](https://json-schema.org/understanding-json-schema/reference/array#length)；[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 說明 Schema 約束與 JSON mode 的區別、支援子集及拒答／不完整回應；[LangChain Models](https://docs.langchain.com/oss/python/langchain/models)／[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output) 說明 Provider／Tool 策略與驗證。來源提供技術依據，不直接核定本專案的 Provider、類別、重試數或 fallback 預設。

<a id="src-04-512-討論提案合併-rewrite-與-multi-query-設定"></a>
### 討論提案：合併 Rewrite 與 Multi-query 設定

**2026-10-16 10:22 提問後的建議，待確認。** 目前 Prototype v0.12 有 None／Rewrite／Multi-query；Rewrite 固定一筆，Multi-query 使用 count，且分別保存 rewrite_prompt／multi_prompt。兩者目前不是只有畫面名稱不同，也尚無真實 Engine 生成實作。不要把共用輸出 Schema 提案描述成現有已共用的執行程式。

建議保留同一 Query Transformation 模組，UI 簡稱 Query Rewrite，以啟用／停用、產生 Query 數量 N、include_original、llm_ref 與一份有效 Prompt 控制：N=1 表示單 Query 改寫，N>1 表示多個檢索表述，停用則直接沿用原始問題、不呼叫模型。多筆時 Prompt 建議描述不同表述／搜尋角度，不能只靠改數字就保證多樣性。

數量設定由平台動態帶入 Schema，queries 的 minItems／maxItems 同為 N，並供實際 Provider 支援的結構化生成與後端驗證使用。Prompt 可自由描述改寫內容，格式／型別／筆數則由平台的 I/O 契約管理；可提供 query／count 變數及固定格式要求預覽，但不依靠使用者手寫「輸出幾筆」才建立限制。Prompt 與設定衝突時仍只放行通過 Schema／語意驗證的結果，不能讓 Prompt 覆寫所選 count。語法與筆數合格不代表保留原意或足夠多樣，後者需人工／Evaluation 驗證。

此為單一方法與共用執行邏輯的候選，不新增另一個 Pipeline 模組。舊 Rewrite 映射 N=1，舊 Multi-query 保留原 count；取原先啟用的 Prompt 為新有效 Prompt，另一份舊草稿的保留／可恢復政策需 Q-002 核定，不能靜默刪除。None、include_original、LLM 引用、逐 Query／跨 Query 融合語意維持一致。採用後應同步 SDK、Registry、AI 助手、UI、範例與驗證；本輪只記提案，不更動原型／正式 Config 枚舉。

<a id="src-04-52-retrieval"></a>
### Retrieval

**目的**：選已索引的全文／向量欄位，自動推導 Dense／全文／Hybrid；後端由 Binding 繼承。

**處理**：

1. 取得對應 Config／Binding，確認 Profile 與資料就緒。
2. 將預設 filters、本次 filters、可信 ACL 以 AND 合併，驗證欄位／operator／值。
3. 建立每個 Query × 全文／向量欄位的路徑；向量路徑依其 Profile 使用 query encoding。
4. 每路在合法候選範圍內取 per_route_k，保留實際回傳的 rank、分數、方向與命中 Query。若 Adapter 在 ES 內部完成融合，接收已融合的一份清單並記錄計分設定；不要求憑空還原未回傳的分項清單／排名。
5. 轉換距離為越大越相關的 relevance；保留 query／route identity，依核定計畫及 chunk_id 對齊融合。
6. 按四個已確認位置取上限：搜尋 Top K、Retrieval 後合併 Top N、模型評分後 Top N、Reranker 後合併 Top N。每個上限只作用於該步輸出的各清單；逐 Query Rerank 後才跨 Query 融合時，不能提前攤平成全域清單。
7. 在 Rerank／檢索結果消費端 使用候選前批次取回所需 fields／metadata，保留各路排序與身分；vectors 可省為 {}，下游無須知道 MongoDB 或 FAISS。

**實作狀態**：Prototype v0.12 已提供 [Builder UI／Backlog](07_builder_ui.md) 的兩層時點 UI 與有效計畫推導；未實作真正的搜尋／融合。單一路是否略過融合仍依有效計畫判斷，文件分組不以清單數量為必要條件。

已確認的 UI 範圍：同一 Query 多路合併、跨 Query 合併，各自可在 Retrieval 後或 Reranker 後執行；兩者新建預設勾選且在 Retrieval 後。先逐 Query Sum Score、再跨 Query RRF 是可表達情境。具體分數方法、正式配置 Schema 與 Adapter 支援仍由 Q-014 核定，原型展示初值不等同新增產品決策。

Inference 的業務 Input／Output 統一為 `list[QueryContext]`（JSON root array），沒有 InferenceState 外框。QueryContext 固定 ori_query、query，並提供預設空值的 filters、result_sets、metadata。ResultSet 只有 key／items；ResultItem 只有 chunk／選填 score。只傳目前有效資料，處理後替換；歷史與診斷寫 Logs。items 順序就是排名，RRF 使用陣列位置。數值 score 經 Adapter 統一為越大越好，Sum Score 仍需驗證完整分數及可比性。 不限制合法流程只能選 Plan A／B。

- Sum Score（ES 內部 Hybrid 預設；平台跨清單可另選）：`sum(weight × relevance_score)`；未命中該路為 0；來源權重與已核定轉換顯式配置；不因選 Sum Score 就默默正規化。
- RRF：`sum(1 / (k + rank))`；各路 rank 從 1；預設 k=60。

原始 BM25／向量分數尺度可能不同；等權 Sum Score 不代表相同實際影響。ES 內部計分與平台跨清單融合分開；後者原型預設 RRF，正式 Adapter 必須驗證分數可比性。距離轉換、同分順序、各路候選截斷的評估仍需 Q-011／Q-014。

同文件片段分組不是 chunk_id 去重。max_chunks_per_document 仍待定。融合計畫的具體規格追蹤 Q-014：若先逐 Query Rerank 再跨 Query 融合，需定義 Rerank 的問題、每路 Top-N、跨路相同 Chunk 與分數比較，不能只搬動一條流程箭頭；Rerank=None 時也不能無聲丟掉必要融合。

**驗收**：同 Chunk 多路命中按計畫去重；少於 K 或零筆為合法；多路套用相同授權；融合可人工驗算；無效 filter 拒絕而不變無條件搜尋。合併時點核定後，另驗證逐 Query／跨 Query 與 Rerank 次序、各階段截斷及 Trace；不能只有策略下拉選單而沒有實際路徑變化。

<a id="result-processing"></a>

<a id="src-04-521-resultset-後處理與共同排序"></a>
### ResultSet 後處理與共同排序

2026-10-15 14:24～14:31（Asia/Taipei）確認後處理收斂為三類：

| 操作 | 輸入／行為 | 輸出 |
|---|---|---|
| 去重＆合併 | 對選入清單依 group_by 分組、merge_key 對齊，再依方法計分 | 每個處理群組的新清單；Sum Score／RRF 為合併方法，不是額外一類操作 |
| 取 Top N | 對已排序的每份選入清單保留前 N 筆 | 分數／方向保留，候選不足時回傳可用數量 |
| 新模型算分 | 依明確 Query、服務與內容欄位評分 | 新分數及來源對應；具體缺項／服務限制仍待 Q-003 |

Inference 的業務 Input／Output 統一為 `list[QueryContext]`（JSON root array），沒有 InferenceState 外框。QueryContext 固定 ori_query、query，並提供預設空值的 filters、result_sets、metadata。ResultSet 只有 key／items；ResultItem 只有 chunk／選填 score。只傳目前有效資料，處理後替換；歷史與診斷寫 Logs。items 順序就是排名，RRF 使用陣列位置。數值 score 經 Adapter 統一為越大越好，Sum Score 仍需驗證完整分數及可比性。 三種操作後各份清單有序，Top N 取目前前 N 筆；None 不取消必要的後置合併。兩層合併／四處 Top N 見 Builder UI／Backlog手冊；Config 細節仍見 Q-014。

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

**處理**：從選定 ResultSet 的 Chunk.fields 取評分內容，保留候選 index 對照；驗證 index 唯一且在範圍內、score 有限，映回相同 Chunk，覆寫目前 score，再排序與取平台設定的 Top N。舊分數不放在業務物件，不改文件／ACL 或生成新候選。None 不評分、不使用其評分後 Top N，但仍執行配置的後置融合；零筆不呼叫服務。服務端 top_n 與平台保留數的邊界如下。

**驗收**：不生成新 chunk_id；重新 rank；保留原 Retrieval Trace。串接 Timeout／錯誤時不假裝 Rerank=None。

**與最新結果操作的對齊**：Rerank 是「新模型算分」的一種方法；模型輸出經共用排序與 Top N，名次由 items 陣列位置表示，不新增 rank 欄位。Top N 保留為可獨立描述的操作能力，但最新 UI 不要求獨立卡片，而是動作的收尾參數；Prototype v0.12 的 Reranker 輸出 Top N 預設 3，見 [Builder UI／Backlog](07_builder_ui.md)。原型 API 說明要求 top_n 等於輸入 documents 數、回應完整評分，再由平台依 UI 上限截斷；正式 Adapter 的完整覆蓋驗證與服務上限仍待 Q-003／Q-014，不能默默依服務預設值少回候選。

**待決**：Q-003、Q-014、Q-017、Q-023；內容欄位分隔、輸入極限、全候選評分與服務回傳缺項政策需核定。

<a id="src-04-54-最終檢索輸出"></a>
### 最終檢索輸出

Inference 在完成配置的 Fusion／Rerank／Top N 後，直接回傳 QueryContext[]；各 ResultItem 包含 Chunk 與選填 score，名次由 items 順序表示，無歷史 lineage。跨 Query 合併停用時保留分組結果，不任意再融合一次。API 包裝見 [Runtime API／部署](06_runtime_api_and_deployment.md#src-07-3-平台管理資料與儲存)，最終結果選擇與版本政策仍由 Q-014／Q-019 核定。

不呼叫回答生成模型、不建立答案 Prompt／Context Budget，也不回傳模型生成的 answer 或 citations。Embedding、Rewrite 與助手所需服務仍依其各自契約使用。

<a id="541-討論提案預設格式與進階自訂-json-輸出"></a>
舊 相關章節 答案 JSON 格式提案已撤銷；此錨點僅保留供舊文件連結遷移。

<a id="src-04-6-evaluation-邏輯"></a>
## Evaluation 邏輯

獨立 Engine 測試可直接對本機 Engine Target 執行；Builder Runner 也可透過 Runtime Client Target 呼叫相同功能。**評分邏輯在本層，工作排程、狀態與報告保存由 Runtime API／部署手冊 管理**。Runner 使用相同公開 Query API；精確 Target Schema 由 Q-018／Q-019 核定，不能重寫不一致的檢索邏輯。

建議 QARecord：case_id、question、relevant_document_ids?、relevant_chunk_ids?、metadata_filter?。DatasetRef／Target 綁定 System、Config、資料版本、Engine／模型／Judge Profile。

| 指標 | 必要輸入 | 要定義的語意 |
|---|---|---|
| Recall@K／MRR | relevant IDs、實際候選與排序 | Chunk／Document 層級、Rerank 前或後、K |
| Latency／Usage／Error Rate | 各題 Trace／結果 | 失敗題不能任意排除 |

缺 Ground Truth 的指標應拒絕或明示 skipped，不能填 0 假裝已評分。relevant IDs 缺失與空清單不同；Chunking 改變後舊 chunk-level 標註不可直接沿用。詳細首批指標、Dataset Schema、Gate、Target API 與 Judge 見 Q-018。

<a id="src-04-7-客製化與擴充"></a>
## 客製化與擴充

<a id="src-04-71-開放範圍與共用契約"></a>
### 開放範圍與共用契約

Module Developer 可針對各 Module 實作 Component；不再只把 Chunking／Rewrite／Rerank 視為可客製範圍。各 Module 的首批 SDK 介面與方法依 M0～M2／M6 逐步提供，未交付的介面不得宣稱已可擴充。Generation 不屬本產品 Module，不能藉自訂 Component 默默重新加入固定 Pipeline。

同一 Module 的公開 I/O 與語意由平台維護，Component 必須相容；Component 自身 Config 可以不同。可使用契約明定的擴充欄位或具名稱／版本的能力宣告，不能自行增改必要頂層 key、把字典任意形狀視為相容，或要求下游默默猜測結構。公開契約可經版本化演進，並非永遠不能改。

IngestionDocument／ParsedDocument／Chunk 的現行草案分別引用 資料契約手冊 與 schemas/。ParsedDocument 已收斂為四鍵外層與平面 units，Chunk 以 unit_index 追溯來源；正式版本／SDK 及細節凍結見 [Q-002](08_plan_and_decisions.md#parsed-document-schema-pending)。不新增直接匯入 Chunk／vectors 的入口。Inference 沿用 05 的 query-context-list/0.3-draft，ResultItem 直接引用共用 Chunk，不另立第二套型別。

<a id="src-04-72-component-必須宣告與配合的行為"></a>
### Component 必須宣告與配合的行為

| 項目 | 要求／規劃 |
|---|---|
| 身分與設定 | component_id、實作版本、模組類型；Config Schema 列明參數型別、預設值、必填／條件必填、限制與說明；與 package／SDK 版本分開追蹤 |
| I/O 與語意 | 宣告相容的 Module Input／Output 型別與 Contract 版本；驗證來源、ID、欄位繼承、分數方向與引用等不變條件，共用契約由平台維護 |
| 能力相依 | 宣告 requires／provides；包含 Parser 輸出 Unit 欄位／文字格式、索引能力、Tokenizer、向量維度／模型及配套 Component 相依；例如 Indexing 與 Retrieval 可讀寫的 artifact 版本 |
| 執行生命週期 | 宣告 async／batch／streaming 支援；依 Engine 規範初始化、執行與釋放；可中斷能力須明示，首期不提供文件工作取消 API；具體簽名留 Q-002／Q-017 |
| 資源需求 | 列明外部 API／DB、Secret 邏輯引用、暫存／持久化儲存、CPU／Memory 的最低／建議需求與測量前提，以及 DEV 測試服務需求；透過受控 RunContext／服務解析介面取得資源，不把憑證寫入 Config、輸出或 Trace |
| 版本與變更影響 | 宣告相容的 SDK／Engine／Contract 版本；逐項說明實作升級或有效參數改變後，是否須重新 Parsing、Chunking、Embedding、重建 Index 或只重測 Inference；由 Engine 依相容政策判定，不只信任作者宣告 |
| 維護與驗收 | 提供維護者、用途／限制、範例 Config、輸入／預期輸出、固定測資、契約／語意測試、錯誤案例及相容版本測試 |

2026-10-28 配套核對補充：以上資源宣告描述方法需求，實際 API URL／Secret 綁定、儲存與 CPU／Memory 配額放在部署設定，不能混入跨環境共用的邏輯 Config。CPU／Memory 需求應註明資料規模、Batch／併發與測試條件；未量測時明示未知或估計，不能填示例數字冒充已驗證最低需求。首版不承諾自動由單一 Component 需求計算整個 Runtime 的資源配額，彙整與部署驗證細節留 Q-021／Q-027。

DEV 服務宣告須區分「所需服務／能力」與「平台當前是否有核可測試服務可綁定」。有平台服務才可使用 DEV test use；沒有時明列需自行提供的設定，不能因宣告就假設平台供應。FTEST／ENT 由使用單位提供對應服務／Secret 綁定。需求內容可先以套件說明與驗收材料交付，機器可讀宣告的欄位／格式留 Q-002／Q-022。

變更影響需說明觸發條件與最早受影響階段；例如重新 Parsing 可能連帶重做後續 Chunking／Embedding／Indexing，不能把各階段視為互不相關的勾選。是否能重用中間結果、所需來源是否仍可取得，以及索引切換／回復政策依 Q-008～Q-010／Q-015，不預設平台一定保留所有中間資料。

共用邊界：Config 驗證 → Input Validation → 執行政策 → 自訂邏輯 → Output Validation → 來源／ACL／語意檢查。Pydantic 不取代「Rerank 只能選候選子集」等語意驗證。

<a id="src-04-73-成對擴充與-graphrag-邊界"></a>
### 成對擴充與 GraphRAG 邊界

Parser／Chunker 或 Indexing／Retrieval 可以由同一 Component package 成對交付，透過能力與 artifact 版本檢查相容性，不以 repo 名稱判斷。新增 Component 若仍遵循既有 I/O，就可接回既有 Pipeline。

GraphRAG 是擴充需求的例子，不是只註冊一個 Retrieval 就保證支援所有策略。若方法內部使用圖資料並回傳符合契約、可追溯的 Chunk 候選，可沿用既有下游；若需要實體／關係／社群摘要等新產物或跨模組新步驟，須先討論契約與流程擴充。不能將無對應來源的摘要偽裝成原始 Chunk。Component 內部可以使用自選框架，但跨模組邊界仍使用平台公開契約。

<a id="src-04-74-開發與發布邊界"></a>
### 開發與發布邊界

第一階段依已確認的兩個 repo 分工，使用本機 IDE＋rag_engine 內的 SDK／Component 範本，在 components 目錄開發並提交 PR；經契約／整合測試與審核後，由同一 repo 的 CI 建置包含 Engine、核可 Components 與 Runtime API 的完整 Runtime Image。純方法變更不必修改 Engine 核心；共用 I/O／SDK／執行政策變更由 Engine Developer 審查，跨模組影響一起驗證。平台負責可用 Component 目錄、測試服務與執行結果，不先建瀏覽器程式編輯器、任意 Python 上傳或 Plugin Marketplace。正式發布權限、套件建置工具及隔離政策仍由 Q-022 核定。

Schema 驗證與 RunContext 介面不是程式隔離邊界；同程序 Python package 仍具有程序權限。若後續允許不受信任程式，須另定執行隔離、網路／Secret／資源限制。既有「共享 Runtime 不任意 exec 使用者程式」限制繼續適用。

<a id="src-04-75-builder助手與部署一致性"></a>
### Builder、助手與部署一致性

Builder 與 AI 助手使用目標 Engine／Runtime 實際支援且核可的 Component 目錄、Config Schema 與能力相依；不各自維護另一份 Component 清單。方法發布不等於所有 Runtime 已安裝，也不自動替換既有 System 的版本。使用者可看到不可用／不相容方法及原因，選擇必須通過相同 Engine Validator。

rag_platform 與 rag_engine 的服務邊界由 Runtime API／Component 目錄承接，接口細節見 Runtime API／部署手冊。若 API／Config Schema 相容且既有表單可呈現，新 Component 經 Runtime 更新即可提供 Builder 選用；若修改了不相容接口或需要新增 UI 控制項，仍需協調 Builder 更新。套件集中於同 repo 不代表任何 Runtime 改動都免重新部署；採用新版的方法／Engine 必須經相容測試並部署該 Runtime Image。

基本設定可依 Config Schema 產生表單，跨模組連動仍需能力規則與顯示資訊；不能承諾任何自訂 UI 都只靠 JSON Schema 自動產生。實際表單／版本呈現列於 [UI Backlog：UIB-010](07_builder_ui.md#src-10-3-累積需求處理狀態)，本輪不修改 Prototype。

DEV 與 FTEST／ENT 維持相同方法選擇／解析版本與邏輯 Config，環境服務綁定分開；交付需驗證目標 Image 包含所需方法與相依套件。僅匯出 YAML 不會自動交付 Component 程式。更新 Component 後重測／重建的判斷依 Q-015，不以版本號單獨認定索引相容。

開發者實作步驟、Python 介面示意與交付檢查見 [Engine／Component 開發](#src-11-2-開發模式與-repo-分工)；決策狀態以 [計畫與決策：Q-022](08_plan_and_decisions.md) 為準。

<a id="src-04-9-engine-完成條件"></a>
## Engine 完成條件

- 不啟動 Builder／HTTP，就能用完整 Config 跑真實 ingest／query。
- Config、Registry 與下游欄位相依可驗證；缺服務／能力得到可定位錯誤。
- Local Memory／MongoDB／ES 的差異被 Adapter 封裝；同一對外 Contract 不依賴框架內部物件。
- 固定測試可驗算 Chunk／offset／fusion／Filter／來源追溯；真實模型／搜尋另有 integration 證據。
- 在乾淨環境以 rag_engine 的 Component package 建置產物驗證安裝、註冊、設定、單一 Component 與完整流程，避免靠原始碼路徑或私有匯入才能執行；不要求另建 repo，也不能靠修改 Engine 核心或 Builder 原始碼才加入每個普通 Component。
- 重複識別、缺失套件、不相容版本／結構／artifact、違反語意的輸出均可定位失敗；Image／方法版本可追溯，升級不默默改變既有 System。
- 尚未核定能力回報不支援，不以 Mock 或靜默 fallback 代表完成。

開發階段與驗收資料見 [計畫與決策](08_plan_and_decisions.md)。

<a id="src-05-5-共用執行與錯誤物件"></a>
## SDK 執行物件、Context 與內部錯誤草案

下列延續舊 04 的設計方向，正式欄位必填與狀態仍由 Q-002／Q-017 核定：

| 物件 | 建議欄位 |
|---|---|
| ModuleConfig／ComponentSelection | 23 的共同選擇草案為 component_id、implementation_version、parameters；module_type 由 slot／Descriptor 推導，I/O 版本由 Registry／SDK 核對，服務邏輯引用依所選參數 Schema；完整包裝待 SC-01／02 |
| RunContext | workspace_id、system_id、config_revision、run_id／request_id、trace_id、deadline、attempt、可信 auth_scope；環境／部署綁定另明確記錄 |
| ModuleResult[T] | status: succeeded／partial／failed，data、errors、warnings、metrics |
| ModuleError | SDK 內部錯誤草案：code、module、message、retryable、item_id?、details?；對外 HTTP／狀態 error 核心依 21 的 code／message／module，輸入驗證另附 path，不直接透出內部包裝 |
| ExecutionMetrics | duration_ms、input_count、output_count、token_usage?、provider_request_id? |

failed 時 data 為 null；partial 必須能對應成功／失敗／skipped 項目，不能默默少資料。哪些模組允許 partial 及如何提交資料仍受 Q-009 限制。HTTP 任務狀態不是 ModuleResult.status，見 Runtime API／部署手冊。

2026-10-29 D-43：上表以 component_id 選擇具體 Component，module_type 表示所屬 Module；它們與 Component Instance 的 node_ref 分開。D-54 之後 ResultSet 只有 key／items，已無 method／operation 等紀錄欄位；方法選擇留在 Config，過程寫 Logs。舊 Config／Prototype 的選擇欄位需按版本遷移，詳見 [架構與責任：名詞對照](01_architecture.md#src-03-31-系統組成與管理階層)。

未知 Token Usage 為 null／省略，不填 0。Secret 與敏感原文不進錯誤／追蹤。使用者無權設定可信租戶／ACL Context。

<a id="config-spec"></a>

<a id="src-11-2-開發模式與-repo-分工"></a>
## Developer：開發模式與 repo 分工

<a id="developer-flow-blocks"></a>

<a id="src-11-local-component四個-block-看開發流程2026-10-29"></a>
### Local Component：四個 block 看開發流程（2026-10-29）

總覽見 [01 L1 使用流程圖](../diagrams/01_user_system_l1.png) 的最下層；Module 與元件關係見 [03 Module／Component 示意圖](../diagrams/03_module_component_concept.png)。

| Block | 要完成的工作 | 主要交付／銜接 |
|---|---|---|
| D1. 下載 repo / 確認開發 contract | 取得 rag_engine／SDK，選定功能分類，確認該 Module 的 I/O、語意及相依要求 | 明確的元件用途與契約／設定需求 |
| D2. 開發 Component | 在 components 目錄實作邏輯、Config Schema、UI hints、能力與資源宣告，準備七項交付材料 | 可安裝／註冊的 Component package 與範例 |
| D3. 測試與 PR 審查 | 單元／契約／Engine 整合測試，提交同 repo PR，由 CI 與審查者核可 | 通過對應契約與整合驗收的元件版本 |
| D4. 發布並更新 Retrieval Engine Library | 交付流程建置含 Engine＋核可 Components＋Runtime API 的完整 Image，更新選定 DEV Runtime 並驗證 | Builder 讀取該 Runtime 的 Component 目錄／Schema，使用者可選用 |

D1～D2 主要由 Module Developer 完成；D3～D4 涉及審查者、CI／發布與平台部署權限，不表示每位開發者都能直接更新共享 Runtime。發布 Image 與更新執行環境分開，只有採用新版的 Runtime 才提供新元件；既有 System 不自動換版，FTEST／ENT 仍依相同 Image／邏輯 Config 交付。詳細流程見 [Component 開發相關章節](#src-11-5-安裝import-與-registry)～7，精確 SDK／命令／權限仍為待決。

D4 的標題統一為「發布並更新 Retrieval Engine Library」，指共用 Engine／Components 與完整 Runtime Image 的版本交付；實際採用新版仍更新選定的 DEV Runtime，部署邊界不變。

內建 Components 指平台規劃交付的可選項；每個 System 依 Config 選用，不是把某個 Module 的所有 Components 一起執行。自訂 Component 與內建元件走相同契約／Registry；Builder User 不需撰寫程式。Indexing／Retrieval 可能需要成對擴充；Parser／Chunker 共用 Units，但仍需文字欄位與格式能力相容，仍依能力檢查，不因放入元件目錄就自動相容。

[03 圖](../diagrams/03_module_component_concept.png) 上半部恢復完整 Module／Component 目錄、既有內建／自訂選項與 Developer 交付流程；8 個 Module 各提供 Remote API Component 作為目標選項，Chunking 加入示例 XXX_component（Developer Local）。下半部同一 Library 配 Config A／B／C 建立三個 System：A 直接使用內建；B 的 Chunking 選 Library 中已核可的 XXX_component；C 的 Parsing 由 Retrieval Builder 提供的 Remote API Adapter 呼叫 Developer 的 Parsing Service。詳見 [圖說](../diagrams/03_module_component_concept.md)。每個 System 展開 5 個 Ingestion Modules 與 3 個 Retrieval／Inference Modules，A／B／C 是配置後實例，不要求三套 class。Remote API 可交付 Image 或既有 Endpoint；URL／Secret／Image 放部署設定。共用服務／程序邊界、方法可用性、I/O 及格式相容仍依 Engine 與資料契約手冊，不因圖中新增選項就視為已實作。

2026-10-28 已確認兩個 repo：`rag_platform` 管理 Builder 前後端與整合，`rag_engine` 集中 SDK、Engine、Components／Adapters 與 Runtime API。Module Developer 使用本機 IDE，在 rag_engine 的 components 目錄依 SDK／範本開發，提交 PR 後由同一 repo 的 CI 測試與交付 Runtime。這取代先前以獨立 Component repo 為預設的建議；精確內部目錄、套件名稱及發布工具仍待 Q-001／Q-022 核定。

| 程式所在位置 | 內容 | 誰維護 |
|---|---|---|
| rag_platform | Builder Frontend／Backend、管理資料與 Runtime／助手整合 | Platform Developer |
| rag_engine 的 SDK package | I/O 型別、Module 介面、Config／RunContext、契約測試工具 | Engine Developer |
| rag_engine 的 Engine／Runtime API | Registry、組裝、執行、資源管理與 API | Engine Developer |
| rag_engine 的 components 目錄 | 各 Module 的內建／客製 Component、Adapters、第三方依賴、宣告、範例與測試 | Module Developer；共用介面變更由 Engine Developer 審查 |

components 目錄可依 Parsing、Chunking、Indexing、Retrieval 等 Module 組織，容納各團隊方法及Parser／Chunker 以及成對 Indexing／Retrieval。SDK、Engine 與 Components 可在同 repo 保留可分別安裝的 Python package，新增 Component 仍只依賴 SDK 公開介面，不複製型別或依賴 Engine 私有類別。完整整合測試使用相容 Engine；新增標準介面下的方法應不需要修改核心。

建議範本包含下列路徑（相對於 rag_engine repo；並非已存在的檔案）：

| 相對路徑示意 | 用途 |
|---|---|
| `components/pyproject.toml` | Component package 的名稱／版本、相依套件與 entry point 宣告 |
| `components/src/rag_components/chunking/team_a_custom.py` | Chunking 分類下的團隊 Component 與設定實作 |
| `components/tests/` | 契約、語意、例外及 Engine 整合測試 |
| `components/examples/` | 小型輸入、預期結果、有效 Config 與服務需求 |
| `components/README.md` | 用途、限制、支援版本、執行方式與維護者 |

在同 repo 透過 PR 審查區分 Component 與 Engine 核心的維護責任，權限與發布核可方式仍由 Q-022 核定。首期可集中建置一個 Component package，後續有必要再於同 repo 拆分套件；repo 數量不隨方法數量增加。

首期不因開放開發而要求另建 Web IDE 或開發者入口網站。發布權限不等於可以讀取所有 Workspace 資料；使用平台測試服務仍依各環境授權。

<a id="src-11-21-remote-developer-的四個步驟"></a>
### Remote Developer 的四個步驟

1. 確認單 Module 或連續 Pipeline 的邊界 Contract；若含 Indexing，宣告相容 Retrieval／索引能力。
2. 實作符合 API Contract 的 Service／必要適配，交付 Manifest、可選 Config Schema／UI hints、能力及測試材料；不強制 FastAPI 或 Component ABC。
3. Image 模式提供 Port／Probe／設定注入／資源與依賴描述；External 模式由 Developer 部署，與管理者登錄各環境連線及固定能力。
4. 審核註冊後在 DEV 驗證，Builder User 從選單使用；Image 模式由平台管理部署，External 保持 Developer 維運。

第一版 External 採固定資料空間，不提供 data_space_id；Image 需可綁定獨立儲存範圍。單純新增相容的服務宣告不要求重建 Runtime；新增不支援的 Adapter／協定或邊界能力仍需更新 Engine／Runtime。Manifest 及協定正式格式未凍結，細節見 [Engine／Component 開發](#src-11-2-開發模式與-repo-分工)。

<a id="src-11-3-識別版本與相依能力"></a>
## Developer：識別、版本與相依能力

| 概念 | 示意 | 用途 |
|---|---|---|
| module_type | `chunking` | 決定套用哪個 Module 介面與 I/O 契約 |
| component_id | `team_a.chunking.custom` | Config／Registry 查找方法，不是 Python import path |
| Python class | `TeamChunker` | 實作符號；不同 package 可有同名 class |
| implementation_version | `1.0.0` | 該 Component 實作版本 |
| distribution package | `rag-components`（暫名） | rag_engine 內的方法安裝單位，可含多個 Component；不表示另有 rag_components repo |
| import package | `rag_components`（暫名） | Python 程式 import 時使用的名稱 |
| Contract／SDK／Engine 相容範圍 | 由已核定版本填入 | 決定型別、接口與執行環境能否配合 |

component_id 的名稱空間由平台管理；同一有效 Registry 不接受相同 component_id＋實作版本的不同實作。調整 max_tokens 等使用參數不需要建立新 component_id；修改實作需可追溯的新發布版本。Package 版本與 Component 版本可以不同，但不能在不更新 package 的情況下替換其發布內容。

除型別外，方法應宣告所需與提供能力：例如 Chunker 需要哪些 Unit 文字欄位／Markdown 格式／Tokenizer、Retriever 需要哪種 Index artifact／版本。Schema 形狀相容不等於語意或索引相容，驗證規則見 [Engine／Component 開發](03_engine_and_components.md#src-04-7-客製化與擴充)。宣告精確欄位及版本遷移由 Q-002／Q-015／Q-022 核定。

<a id="src-11-4-python-component-介面示意"></a>
## Developer：Python Component 介面示意

以下只展示開發責任，**類別、import 路徑、建構方式與 async 簽名尚未實作或凍結**。範例刻意保留待實作主體，不提供假切分演算法，也不重新定義 ParsedDocument／Chunk。

```python
from pydantic import BaseModel, Field

# 以下 rag_engine_sdk 路徑與型別為規劃中的公開介面。
from rag_engine_sdk import (
    ChunkingInput,
    ChunkingComponent,
    ChunkingOutput,
    ModuleResult,
    RunContext,
)


class TeamChunkerConfig(BaseModel):
    max_tokens: int = Field(default=500, ge=1)


class TeamChunker(ChunkingComponent):
    component_id = "team_a.chunking.custom"
    implementation_version = "1.0.0"
    config_type = TeamChunkerConfig

    async def run(
        self,
        data: ChunkingInput,
        config: TeamChunkerConfig,
        context: RunContext,
    ) -> ModuleResult[ChunkingOutput]:
        # Engine 固定並驗證本次 Config，再注入正確 System 的資源。
        # 實作切分、來源對照與合法 metadata 繼承後，
        # 回傳公開 ChunkingOutput，由 Engine 再驗證輸出語意。
        raise NotImplementedError("待 Chunking 契約核定後實作")
```

`ModuleResult` 的邏輯用法沿用 04：業務輸出位於 data，metrics／errors 不混進下游業務物件。ChunkingInput 的業務內容引用 14 的 ParsedDocument，ChunkingOutput 引用 15 的 Chunk 清單；不得重新宣告另一份欄位形狀。Module-specific Input／Output 包裝與實際方法簽名由 Q-002 決定。完整方法宣告另需 Config Schema、相依能力、相容版本與維護資訊，範例 class 不代表宣告已齊全。

D-62 已確認共用 Flow／Executor，每次呼叫傳入本次 Component Config；上述簽名仍是 SDK 草案。無狀態且可安全併行的實例可共用，有狀態或特定資源需求者由 Resolver 分開；共用實例不得把本次 input／config／output 保存到跨請求可變 self。資源生命週期與精確 Resolver 介面見 [Engine／Component](#src-04-1-目標與依賴邊界)。

Component 不自己重建 Engine 的重試、排程與授權流程。必要 Client／Tokenizer 等經受控資源介面取得，初始化與清理配合 Engine；禁止在輸入文字、Config 或自訂輸出中夾帶可執行指令交給 Engine 動態執行。Schema／RunContext 不等於程序隔離，核可與隔離邊界見 [Engine／Component 開發](03_engine_and_components.md#src-04-74-開發與發布邊界)。

<a id="src-11-41-讓-component-可由-builder-設定"></a>
### 讓 Component 可由 Builder 設定

具體候選格式與 Parser／Chunker／Embedding／Remote 對照見 [Descriptor](04_component_descriptor.md)及 [examples/component_descriptor](../examples/component_descriptor/README.md)。這些是待決格式／離線預期結果，不是已發布 SDK；實作交付仍需待核定介面與真實契約測試。

D-67 補充：Developer 另提供共用 I/O Contract 引用、固定或依 Config 細化的資料規格，以及上游選項／相依條件。首版六類純宣告由 Engine 通用解析器處理，不要求每個 Component 自寫 resolve_io_schema；Local／Remote 等價交付，完整內容見 [Descriptor](04_component_descriptor.md)。不再以 User 手填的頂層 document_schema 取代 Parser 輸出宣告；正式語法／SDK 尚未凍結。

依 D-42 與 [Descriptor](04_component_descriptor.md)，開發者先宣告 `config_type`；共用父類別輸出 Config Schema，Registry 檢查，不必重寫同一份 Schema 產生函式。需要特殊顯示時提供 UI hints；動態欄位／LLM 選單另宣告 option_sources，參數相依另列 rules／capabilities，不能只把限制寫在 UI。

Descriptor 為純 JSON，不能包含前端程式／任意 import 或連線憑證。宣告必要控制項／能力版本，提供合法、失效與分支切換案例；無參數方法也需合法空設定 Schema。取得描述不應先初始化 Component 資源。機器可讀格式目前為 `component-ui-0.1-draft`，完整 SDK／Meta-schema 仍待 M0 核定。

最小驗收材料需包含：Schema／設定型別一致、動態候選與 API 直接傳值都驗證、失效引用不被換掉、不適用參數不進有效配置，以及共用問題格式。具體 SUI-01～14 見 [Descriptor：驗收案例](04_component_descriptor.md#src-12-1-目的與已確認行為)。這些補充既有七項交付清單，不代表已完成可執行 Runner。

<a id="src-11-5-安裝import-與-registry"></a>
## Developer：安裝、import 與 Registry

同 repo 中的 SDK／Engine／Components 仍須依套件邊界安裝到使用的 Python 環境。以下是未來已有合格範本／pyproject 與 SDK 時，在 rag_engine 根目錄執行的本機開發指令示意：

```sh
python -m pip install -e ./packages/sdk -e ./packages/engine -e ./components
```

安裝與註冊是兩件事。初期可在受控 Engine 啟動程式中明確 import：

```python
# 規劃示意：registry.register 的正式簽名尚未核定。
from rag_components.chunking.team_a_custom import TeamChunker

registry.register(TeamChunker)
```

後續可用 entry points 宣告安裝套件所提供的方法，以下 group／name 是候選值，不是既有正式規格：

```toml
[project.entry-points."rag_engine.components"]
team_a_custom_chunker = "rag_components.chunking.team_a_custom:TeamChunker"
```

這只是 `pyproject.toml` 的一段，不是完整可發布專案。Engine 先核對核可的 distribution／版本，再載入指定 entry point，取得類別與宣告、註冊至 Registry。不能因套件已安裝或符合 group 就全部執行；不讓使用者在 Config 填任意 Python 路徑。

Runtime 建置時安裝 Engine 與 Components，註冊後依有效 Config 初始化所選方法／外部服務；Builder 透過 Runtime API／Component 目錄選用，不直接從另一個 Image import Python 程式，也不需安裝所有 Components。Component 目錄與設定驗證接口見 [Runtime API／部署](06_runtime_api_and_deployment.md#src-07-58-runtime-component-目錄與-config-驗證邊界)。

Python Packaging User Guide 說明以套件 metadata／entry points 發現及載入 plugin 的方式：[Creating and discovering plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)（查核 2026-10-28）。這支持候選載入機制，並不替本專案決定核可政策、權限或 group 名稱。

使用者的 Config 選擇 component_id、版本引用及參數；Engine 解析成已安裝實作。Config 的正式巢狀結構與版本鎖定檔格式尚待 Q-002，因此這裡不新增另一份看似正式的完整 Config YAML。

<a id="src-11-6-測試與審查"></a>
## Developer：測試與審查

開發者先跑單一 Component 測試，再以相容的 Engine 做整合；平台的 DEV 試跑提供補充證據，不能取代可在獨立環境執行的測試。

| 層級 | 驗證內容 | 例子 |
|---|---|---|
| Config／I/O 契約 | 型別、必填、能力宣告與錯誤定位 | 缺必要欄位、未知欄位、Unit 欄位／文字格式不符 |
| 模組語意 | 對應 Module 的來源／ID／分數等限制 | Chunk 可對回文件；Rerank 不捏造候選；向量維度正確 |
| 方法邏輯 | 固定小型資料與人工可檢查的預期 | Token 邊界、空輸入、Unicode、Filter 與排序 |
| 資源與失敗 | 依 Engine 政策處理中斷、逾時與釋放 | API 拒絕／Timeout；初始化失敗後不殘留連線 |
| Engine 整合 | 用公開介面接入相鄰模組並跑通 Config | 自訂 Parser→自訂 Chunker；成對 Indexing→Retrieval |
| 發布與相容 | 乾淨環境安裝、Registry 衝突、版本與 artifact 檢查 | 缺套件／錯版要失敗，不能改用內建方法蒙混通過 |

固定替身用來驗證邊界與錯誤，真實模型／DB／搜尋另留整合證據；Mock 通過不代表方法品質合格。先用 components 內的一個 Chunking Component 證明 SDK 邊界，再擴充 Parser 與成對 Indexing／Retrieval；將建置好的 package 安裝到乾淨環境測試，確認不依賴原始碼目錄或 Engine 私有匯入即可執行，不要求另建外部 repo。確切工具／CLI 指令需 SDK 實作後補上。

<a id="src-11-7-從開發到-builder-與部署"></a>
## Developer：從開發到 Builder 與部署

建議交付流程：

1. **開發者準備**：在 rag_engine 的 components 目錄加入實作與宣告、固定測資、用途／限制、相容矩陣、外部服務需求及變更影響。
2. **同 repo PR／CI 審查**：測試契約、模組語意、依賴與 Engine／Runtime API 整合，確認可發布內容及維護責任；共用 Contract 改動須同步檢查受影響方法。
3. **建置完整 Runtime Image**：由 rag_engine 的同一交付來源建置 SDK／Engine／核可 Component packages，再與 Runtime API 一起納入 Image。CI 可直接使用本次建置套件，不要求先設私有套件倉庫；工具及對外套件發布方式待 Q-001／Q-022 核定。
4. **更新使用新版的 DEV Runtime**：部署選定 Image，以該版本建立測試 System，依正常 Ingestion／Inference／Evaluation 流程驗證；發布 Image 不等於執行中的 Runtime 已更新。
5. **提供目錄資訊**：Builder 與 AI 助手取得目標 Runtime 的 component_id、設定與能力；API／Schema／表單支援範圍相容時 Builder 可維持原版。需要新型 UI 或不相容接口時，需協調 rag_platform 更新及整合測試。
6. **FTEST／ENT 交付**：YAML 引用包含所需方法的 Runtime Image，保持相同邏輯 Config 與方法解析版本，補齊環境服務／Secret。使用單位自行部署。

發布新版不自動升級既有 System。缺少舊版套件／Image 時須明示無法重現，不靜默換最新版。Component 更新是否須重建索引由實際輸入／輸出及 artifact 相容性決定，不能只看版本字串。Rollback 是否可沿用原索引同樣需要相容檢查。

同 repo 讓 Engine 與 Components 一起驗證／交付，採用新版時仍需更新 Runtime；Builder 的相容改動則可只建置部署 Builder。Runtime 更新重啟造成的 Memory 資料遺失或索引恢復沿用既有政策，完整變更範圍見 [Runtime／部署](06_runtime_api_and_deployment.md#src-07-3-平台管理資料與儲存)。本輪沒有承諾 Component 熱插拔或自動更新所有環境。

不承諾每個 Component 都能自動生成任意複雜 UI：基本欄位可由 Schema 呈現，能力相依、條件卡控與特殊輸入需平台支援。待辦統一記在 10；此流程不新增瀏覽器程式上傳入口，也不把 Runtime 安裝套件變成一般使用者操作。

<a id="src-11-8-待決項與開始時機"></a>
## Developer：待決項與開始時機

| 待決事項 | 何時需定案 | 目前可先做 |
|---|---|---|
| 共用 I/O、ParsedDocument 結構、Config／錯誤與 SDK 公開介面 | M0 正式契約凍結前；Q-002，關聯 Q-004／Q-005 | 整理使用案例、方法需求、Schema 候選與測試資料 |
| Python／SDK／Engine 版本、repo 內部套件目錄、entry point／Factory 形式 | M0～M1 建立可安裝範本前；Q-001／Q-002／Q-022 | repo 邊界已依 D-41 確認；起草同 repo 範本，以顯式註冊驗證最小方案 |
| 發布審核權限、套件建置／選配倉庫與可信程式範圍；若開放不受信任程式則需隔離規格 | Component 程式進共享 DEV Runtime 前；Q-022 | 依已確認的 rag_engine 同 repo 審查／Runtime 交付方向細化，不交付任意程式上傳 |
| 實作／套件版本記錄、既有 System 升級／索引相容與部署鎖定 | 更新既有資料或正式交付前；Q-015／Q-021／Q-022 | 設計相容檢查與失敗案例，不自動升級 |

這些事項不阻擋本輪文件整理；規格定案與工具實作後，再將介面示意換成經測試、可直接執行的開發教學。完整決策狀態只維護於 08，不因本指南提供建議就自動關閉 Q-ID。

<a id="src-16-2-共用-pydantic-contract先給一版具體型別"></a>
## Parser 教學：共用 Pydantic Contract：先給一版具體型別

形狀來源仍是 [IngestionDocument JSON Schema](../schemas/ingestion_document.schema.json)／[IngestionDocument](02_data_contracts.md#src-13-1-已確認方向與責任)，以及 [ParsedDocument 0.2 JSON Schema](../schemas/parsed_document.schema.json)／[ParsedDocument](02_data_contracts.md#src-14-1-唯一共用-schema)。這裡不修改共同 Schema，提供對應的 [contracts.py](../examples/component_development/contracts.py) 供示範使用。

以下為**欄位視圖，省略完整驗證器與設定**；可執行版本以 contracts.py 為準：

```python
from pydantic import BaseModel, Field, JsonValue

class IngestionDocument(BaseModel):
    document_id: str
    source_revision: str | None = None
    content: str | dict[str, JsonValue] | None = None
    base64: str | None = None
    uri: str | None = None
    media_type: str | None = None
    schema_id: str | None = None
    parsing_profile: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

class ParsedDocument(BaseModel):
    document_id: str
    source_revision: str
    units: list[dict[str, JsonValue]]
    metadata: dict[str, JsonValue]
```

完整版本的規則：

- IngestionDocument 禁止未知根欄位；content／base64／uri **恰好一個**，不能同時提供。
- 可選根欄位可以省略，**明確傳 null 不接受**。Python 的 None 只表示未設定；to_payload() 保留省略狀態，不送出未使用的 None。metadata 省略時補 {}，其內的業務 JSON 值可以為 null。
- document_id／source_revision 等識別字串不可為空；content 字串／object 不可為空。支援何種 URI 協定、實際 Base64 解碼／媒體格式另由相容 Parser／resolver 驗證。
- ParsedDocument 必須有四鍵：document_id、source_revision、units、metadata；禁止未知根欄位。units 為非空有序列表，每筆為非空 dict，直接放欄位，不包 fields、不強制 unit_id、不另設 structure。提供 text 時必須為字串。
- 共用 ParsedDocument 不強制一定有 text，以保留進階欄位選擇；本示範 Parser 的能力另外要求非空白 text。
- 形狀驗證與語意驗證分開。本例另外檢查只輸出一份文件、文件 ID／revision 與 metadata 繼承；一般 Parser 仍可輸出多文件，但需另有明確 ID 派生政策。

<a id="src-16-同一組-inputoutput一個多頁字串--多個-unit"></a>
### 同一組 Input／Output：一個多頁字串 → 多個 Unit

Parser Input 仍是 IngestionDocument；text 是 **一個 str**，不是預先切好的 page array。本例用獨立一行的 `=== PAGE N ===` 明確表示頁面邊界，方便示範 Parser 如何辨識頁面。這是本示範 Parser 的文字格式約定，不是平台共用 Schema 的新規定，也不代表所有 PDF 匯出的文字都有這種標記。

完整 [輸入 JSON](../examples/component_development/multi_page_input.json)：

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "content": {
    "text": "=== PAGE 1 ===\n# 設備保養\n## 安全注意事項\n清潔前先斷電，並確認設備已冷卻。\n作業時請配戴防護手套。\n\n=== PAGE 2 ===\n# 設備保養\n## 清潔週期\n每月清潔散熱孔。\n若環境粉塵較多，請提高檢查頻率。",
    "title": "設備保養手冊"
  },
  "metadata": {
    "department": "manufacturing",
    "filename": "maintenance-manual.pdf"
  }
}
```

為方便閱讀，content.text 展開如下：

```text
=== PAGE 1 ===
# 設備保養
## 安全注意事項
清潔前先斷電，並確認設備已冷卻。
作業時請配戴防護手套。

=== PAGE 2 ===
# 設備保養
## 清潔週期
每月清潔散熱孔。
若環境粉塵較多，請提高檢查頻率。
```

輸出仍為 **list[ParsedDocument]**；一份文件內有兩個 Unit，並不是拆成兩份文件。完整 [輸出 JSON](../examples/component_development/multi_page_output.json)：

```json
[
  {
    "document_id": "manual-001",
    "source_revision": "v1",
    "units": [
      {
        "text": "# 設備保養\n## 安全注意事項\n清潔前先斷電，並確認設備已冷卻。\n作業時請配戴防護手套。",
        "title": "設備保養手冊",
        "page": 1
      },
      {
        "text": "# 設備保養\n## 清潔週期\n每月清潔散熱孔。\n若環境粉塵較多，請提高檢查頻率。",
        "title": "設備保養手冊",
        "page": 2
      }
    ],
    "metadata": {
      "department": "manufacturing",
      "filename": "maintenance-manual.pdf"
    }
  }
]
```

本例處理規則：

1. Parser 辨識頁面標記，取出頁碼與頁面文字，移除標記及頁面文字頭尾空白，頁內 Markdown 標題保留。
2. 每頁產生一個 Unit；title 等其他 content 欄位複製到各 Unit，page 由標記推導。document_id、source_revision 及文件 metadata 保留。
3. 頁碼必須為正整數、唯一且遞增，允許有間隔；有效標記前有未歸屬文字、空白頁，或同時提供 content.page，都明確報錯，不自行猜測或覆寫。本示範不處理任意／損壞的分頁標記。
4. 沒有分頁標記時沿用原行為：文字／單筆 JSON 產生一個 Unit。實際 PDF、PPT 或 OCR 的頁面辨識由相應 Parser 實作。
5. Chunker 不再辨識頁面標記；它只在每個 Unit 內以所選文字策略切分，不跨 Unit 合併。page、title 要供下游使用時，仍依 Chunking 的 copy 設定帶入 Chunk.fields。

本例要求明確提供 source_revision，省略時回明確錯誤，不自行假設 v1。共同 Input 仍允許省略；正式自動產生政策依 Q-007。本例只支援直接 content 的文字／單筆 JSON，不支援 URI、Base64、PDF 或已解析 content.units；那些必須選用有宣告能力的 Parser。這不是移除共同輸入的來源選項。

<a id="src-16-3-local-developer實作-parser-abc"></a>
## Parser 教學：Local Developer：實作 Parser ABC

D-62 已確認正式執行方向為共用 Flow，Component 每次接收 input／本次 config／Context，見 [Engine／Component](#src-04-1-目標與依賴邊界)。本文件及可執行教學檔暫保留無演算法參數的 run(data, context) 介面，用來驗證 Parser 邏輯與 HTTP I/O，不是新 SDK 的最終簽名；後續 SDK 整合時再同步更新。Remote 服務不因本地傳入 config 就自動新增 HTTP 欄位。

[local_component.py](../examples/component_development/local_component.py) 定義下面的教學介面：

```python
class ParserComponent(ABC):
    component_id: str
    config_type: type[BaseModel] = ParserConfig

    @classmethod
    def config_schema(cls) -> dict:
        return cls.config_type.model_json_schema()

    @abstractmethod
    async def run(
        self, data: IngestionDocument, context: RunContext
    ) -> ModuleResult[list[ParsedDocument]]:
        ...

    async def aclose(self) -> None:
        pass
```

Developer 的實作只處理解析邏輯；相同 ABC 可讓 Engine 呼叫內建或自訂 Component：

```python
class StructuredJsonParser(ParserComponent):
    component_id = "example.parsing.structured_json"

    async def run(self, data, context):
        documents = parse_structured_json(data)
        validate_structured_json_output(data, documents)
        return ModuleResult(data=documents)
```

parse_structured_json() 辨識 text 中的示範分頁標記，產生多個 Unit；未分頁則保留單一 Unit。此處按頁辨識內容單位，不是依 Token 長度切 Chunk，且不跨頁合併。演算法示意在 [parser_logic.py](../examples/component_development/parser_logic.py)，與共用型別分開。

Engine 取 ModuleResult.data 傳下游；ModuleResult 是本地 SDK 包裝，不是 ParsedDocument 的根欄位。示範 RunContext 只有 request_id；正式受控資源、metrics／errors、初始化及清理介面仍依 [Engine／Component 開發](#src-11-2-開發模式與-repo-分工)／[Engine／Component 開發](#src-11-2-開發模式與-repo-分工) 凍結，不把本教學 dataclass 當完整 SDK。

<a id="src-16-4-remote-developer實作-api不需要-component-abc"></a>
## Parser 教學：Remote Developer：實作 API，不需要 Component ABC

Remote Developer 可只取 contracts.py，或使用等價的 JSON Schema 自行實作。FastAPI 是**選用範本**，不強制框架或語言。

[remote_service.py](../examples/component_development/remote_service.py)：

```python
from fastapi import FastAPI, HTTPException
from contracts import IngestionDocument, ParsedDocument
from parser_logic import parse_structured_json

app = FastAPI()

@app.post("/parse", response_model=list[ParsedDocument])
async def parse(data: IngestionDocument) -> list[ParsedDocument]:
    try:
        return parse_structured_json(data)  # 換成 Developer 的私有解析邏輯
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

此示範 HTTP 約定：POST /parse，JSON body 直接是 IngestionDocument，200 body 直接是 list[ParsedDocument]；不包 ModuleResult／data，也不要求傳 RunContext。FastAPI 的輸入驗證錯誤為 422，本例不支援的來源／未提供版本為 400；**狀態碼與錯誤 Envelope 尚非全平台正式協定**。

<a id="src-16-retrieval-builder-提供的-remote-api-adapter"></a>
### Retrieval Builder 提供的 Remote API Adapter

[remote_adapter.py](../examples/component_development/remote_adapter.py) 仍實作本地 Parser ABC，讓 Engine 使用相同呼叫方式：

```python
OUTPUT = TypeAdapter(list[ParsedDocument])

class RemoteApiParser(ParserComponent):
    component_id = "example.parsing.remote_api"

    def __init__(self, client, endpoint):
        self.client = client
        self.endpoint = endpoint

    async def run(self, data, context):
        response = await self.client.post(
            self.endpoint,
            json=data.to_payload(),
            headers={"X-Request-ID": context.request_id},
        )
        response.raise_for_status()
        documents = OUTPUT.validate_json(response.content)
        validate_structured_json_output(data, documents)
        return ModuleResult(data=documents)
```

API Input／Output 不轉成另一套文件物件；HTTP 序列化／還原由 Adapter 處理。本例只轉送 request_id，不轉送整個可信 Context。Client、endpoint、認證與 timeout 由部署綁定注入；Client 由建立者關閉。正式版還需錯誤映射、資源限制及核定的重試／冪等政策。

<a id="src-16-5-developer-最少要拿到什麼"></a>
## Parser 教學：Developer 最少要拿到什麼？

| 套件／材料 | Local Developer | Remote Developer |
|---|---|---|
| Contracts：Pydantic／JSON Schema、語意檢查與正負測資 | 需要 | 必須遵守；可選 Python 套件或等價語言實作 |
| Component SDK：ABC、Config Schema、受控 Context、生命週期 | 需要 | 不需要；不要求其服務依賴完整 Engine |
| FastAPI 服務與部署範本 | 不需要 | 選用；Image／Endpoint 的 API 相同 |
| 完整 Engine | 整合測試使用 | 非遠端服務依賴；需與 Adapter 做相容測試 |

本例沒有演算法參數，所以不新增 Remote request envelope，body 保持原 Input。未來有 per-System 演算法參數時，要另定參數／初始化協定，不能把任意 Config／連線設定塞入文件 metadata、偷偷借用 parsing_profile，或直接把整個 Config／Secret 傳出去。設定描述與 UI hints 仍需由 Developer 提供並登錄；Pydantic I/O 相同，不代表 UI 參數或語意必然相容。

<a id="src-16-51-metadata-處理提示與選填追溯d-52"></a>
### metadata 處理提示與選填追溯（D-52）

上述禁止任意 Config 傳輸，不禁止 Component 明確支援的文件層 metadata 提示。Parser 可保存合法提示，後續 Component 依自身宣告讀取；例如支援 chunking_mode 的 Chunker 可保留整個 Unit，缺省正常切分，不需通用規則引擎。_rag 追溯由輸出 Component 選擇是否提供；本 Parser 教學與 HTTP body 不因此改寫，見 [Chunk](02_data_contracts.md#src-15-1-共用物件)。

<a id="src-16-6-如何重現"></a>
## Parser 教學：如何重現

以下是獨立教學資料夾，不是正式 SDK 套件。先從 repo 根目錄執行：

```bash
python -m venv .venv-demo
.venv-demo/bin/pip install -r examples/component_development/requirements.txt
.venv-demo/bin/python examples/component_development/test_demo.py
```

要啟動示範 API，可用同一環境執行：

```bash
.venv-demo/bin/uvicorn remote_service:app --app-dir examples/component_development --port 8001
```

測試會以本地 ASGI Transport 跑 FastAPI 與 Remote Adapter，對照 Local 輸出；不呼叫外部模型／服務，也不代表已完成 Image 部署、Secret 管理或正式 Exporter。Shared Schema、Pydantic、HTTP 回應形狀與語意的相容性，都應列為正式 Component 驗收材料。

<a id="src-18-3-service-manifest-與註冊流程"></a>
## C：Remote Manifest 的內容與註冊流程

Developer 提供 Manifest，平台管理者審核並註冊；Builder User 在選單選服務，不自行填寫這些 Developer Service 的 URL、API Path 或 Header。平台提供共用 Remote API Adapter；服務符合支援的協定及邊界 Contract 時，Developer 不必另寫每個 Module 的本地 Component。既有 API 不符時仍需適配程式，不能靠 Manifest 自動轉換任意 Payload。

以下是需描述的資訊群，**不是已定案的欄位拼字或完整 Manifest Schema**：

| 資訊群 | 內容／例子 |
|---|---|
| 識別與顯示 | 穩定服務 ID、版本、名稱、說明、維護者 |
| 執行範圍 | 單 Module 或連續範圍，例如 Parsing～Embedding；一份服務可宣告多個操作 |
| Contract／能力 | 輸入輸出引用及版本、向量／索引能力、requires／provides、相容 Engine／Adapter |
| 可設定參數 | 可選的 Config Schema、UI hints、相依規則、預設值與限制 |
| 呼叫描述 | 操作端點的相對 Path／Method、序列化協定、Timeout、認證需求；不包含 Secret 值 |
| Image 部署描述 | Image 版本引用、Port、健康檢查、資源需求、設定檔／Secret 注入、外部依賴 |
| 外部端點綁定需求 | 所需的連線與認證引用，由 Developer／管理者按環境設定 |
| 驗收與變更影響 | 輸入輸出、失敗案例、契約測試、固定設定／版本、重新 Ingestion／索引相容影響 |

註冊流程：提交宣告與材料 → 審核 Manifest／Contract／Adapter 能力 → 加入核可目錄 → Builder 顯示 → 選擇與驗證 → 解析部署綁定。只有 Manifest 不足以保證服務可執行；目標 Runtime 必須支援該 Adapter、範圍與協定。未部署、連線失敗或版本不相容需顯示原因，不把「已註冊」當作「已 Ready」。不開發專用的 Service UI 或任意前端腳本。

<a id="src-18-4-三類設定與固定服務"></a>
## Remote 的邏輯參數、啟動設定與環境綁定

| 類別 | 提供者 | 保存／傳遞 |
|---|---|---|
| 服務定義 | Developer，經平台核可 | Manifest；描述能力、可調整項目與部署需求 |
| System 邏輯 Config | Builder User | 選定服務／版本、範圍及開放的演算法參數 |
| 環境綁定 | Developer／平台管理者／部署者 | DEV／FTEST／ENT 的 Endpoint、Secret 引用、儲存目標及資源 |

模型語意、Chunk 長度等即使透過啟動設定檔載入，仍屬邏輯參數，不因傳遞方式而變成環境覆寫。Image 模式由邏輯 Config 與環境綁定渲染設定檔，第一版修改啟動設定後重新部署，不承諾熱更新。

Developer 自行部署且已固定設定的服務，可不提供使用者可填的 Config Schema；UI 只顯示能力／固定值與限制，不出空白參數表單。既有 12 的單 Component Descriptor 若需要 config_schema，Adapter 以合法空物件 Schema 表示無可調參數，不要求重寫原服務。固定服務的模型／索引等語意應隨註冊版本記錄；不因使用者未填參數就假定跨環境相容，Endpoint 背後語意改變需重驗證並記錄變更。

若 API 明確支援每次呼叫的功能參數，才由 Manifest 宣告並在 UI 展開；精確參數 Envelope／Header 協定待 Q-019 核定。不把任意演算法／連線設定塞進文件 metadata、借用 parsing_profile 或傳送整個可信 RunContext／Config／Secret；D-52 允許 Component 明確支援的文件層提示（如 chunking_mode），不是任意 Config／授權覆寫。16 的無參數 Parser HTTP 範例維持原 body。

## 描述與開發完成條件

Local 在 rag_engine 受控開發與發布；Remote 以 Manifest／Image 或既有服務交付，不要求提交 Source Code。兩者都遵守公開邊界與 Descriptor／能力／測試要求。七項交付由本手冊的 Component 宣告與配合行為統一維護；正式 SDK／Factory／Manifest／Adapter 與發布細節仍是候選，不把本機教學當完整產品。

Config 相依的 I/O 細化、動態選項、表單及 DS-01～DS-13 統一閱讀 Descriptor 手冊，不在 Engine 重複維護另一套語法。


<a id="repository-layout"></a>
## 候選程式目錄與建置邊界

2026-10-28 已確認 repo 邊界，正式定義見 [§3.7](01_architecture.md#src-03-31-系統組成與管理階層)。以下內部路徑仍是 Q-001 的建議配置，不是已建立的程式或額外 repo：

| Repo | 路徑草案 | 職責 |
|---|---|---|
| rag_platform | `apps/builder_ui/` | 06：正式 Builder UI |
| rag_platform | `services/builder_backend/` | System、Revision、Dataset、Export、Runtime Client 與助手 UI 請求協調 |
| rag_engine | `packages/sdk/` | 05：公開型別／Contract；04：Module 介面、Config／RunContext 與開發工具 |
| rag_engine | `packages/engine/` | Compiler、Registry、Pipeline 與執行政策；具體方法實作放 components |
| rag_engine | `components/` | 各 Module 的內建／客製 Component packages、相關 Adapters、能力宣告與測試 |
| rag_engine | `services/runtime_api/` | HTTP／Job／Engine lifecycle、可信管理與能力目錄接口 |
| rag_engine | `packages/config_assistant/`（建議） | M4 可獨立使用的助手核心，重用共用 Schema／Registry／Validator；M5 由 Builder 串接 |
| 各 repo | `tests/`、`examples/`、部署建置檔 | 各自測試與跨 repo 契約整合範例 |

執行時 Builder UI → Builder Backend → Runtime API → Engine → SDK／Components。Engine 與 Component packages 都依賴 SDK；SDK 不反向依賴 Engine 或 Builder。Builder 可以使用核定版本的共用型別／Client 作本地格式預檢，方法能力與完整 Config 驗證仍以目標 Runtime 的同一 Engine 為準，不安裝全部 Components 或複製組裝邏輯。

Component 開發在 rag_engine 的 components 目錄提交 PR；同 repo 的 CI 驗證 SDK／Engine／Components／Runtime API，產出完整 Runtime Image。rag_platform 依 Frontend／Backend 的服務邊界產出 Builder Image。Repo 數量不限制 Image 數量，也不要求每個方法各建一個服務。建置可使用多階段或內部基底，但正式交付不依賴另一個 rag_components repo 組裝。

M4 助手核心的建議位置在 rag_engine，以便使用相同 Registry／Validator；它仍可透過 Python／API 獨立執行，不需啟動 Builder 或存取 Builder DB。HTTP 宿主、套件可選依賴與 Image 包裝由 Q-001／Q-019／Q-024 核定，不要求 FTEST／ENT Runtime 一定啟用或攜帶助手。M5 保留 UI 草稿、Diff、套用／取消與授權整合的責任，階段順序不變。

技術版本、精確套件名稱／目錄、FastAPI 等 Web Framework、資料庫及建置工具仍待 Q-001／Q-016；已確認的 repo 分工不再列為待選方案。跨 repo 通訊的接口相容、Component 目錄及升級規則見 §5.8／§9.4。


<a id="remote-inference-boundary"></a>
## Remote 推論公開邊界

同一推論 Pipeline 內的 Remote 單 Module／整段都接收、回傳 QueryContext[]，沿用 filters／metadata 與目前有效結果。Config／Secret／可信 ACL 不放在這個 body。ResultSet.key 為穩定路徑／群組；多個 context 可以保留，不為了 HTTP 再融合。HTTP 版本／參數 Envelope 仍待 Q-019；舊 InferenceState body 須明確升級，不靜默混用。


<a id="sdk-schema-description"></a>
## SDK 如何提供設定描述

規劃中的共用 BaseComponent 以 config_type 指向設定的 Pydantic Model，父類別可用 model_json_schema(mode="validation") 輸出 config_schema；ui_hints 預設空物件，特殊呈現才覆寫。不要求每個 Component 重寫同一份 Schema 轉換。

取得描述與 I/O 細化不先初始化模型／DB 或取得 Secret。Local 匯入本身仍是受控程式執行；Remote 使用核可 Manifest 推導描述。這些不是不受信任程式的隔離方案；純 Descriptor 規則與特殊解析機制的界線以 Descriptor 手冊為準。
