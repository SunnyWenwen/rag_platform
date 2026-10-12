# RAG Platform — 模組目的、方法與 I/O Contract

> Version 0.1 · 2026-10-12 · Discussion Draft
>
> 本文件為平台自訂規格草案，不是 LangChain 的原生 API，也不代表功能已實作。技術方向以部門既有 LangChain／LangGraph 生態系為基礎，搭配 Pydantic 明確驗證資料邊界。MVP 使用固定流程，暫不提供任意 DAG 編輯。

## 1. 範圍與設計原則

- Ingestion：Data Import → Parsing → Chunking → Embedding → Indexing。
- Inference：Query Transformation → Retrieval → Rerank → Generation。
- Evaluation：獨立批次流程，可執行 Retrieval-only 或完整 RAG。
- 全文 BM25 模式可略過 Embedding；None 類模組採明確的 pass-through，不能讓 I/O 結構任意改變。
- 每個模組分開設定 **Method（方法）／Implementation（實作或 Provider）／Parameters（參數）**。例如 Hybrid 是方法，Elasticsearch 是後端，Top-K 是參數。
- Platform Contract 為穩定邊界；Adapter 負責轉換 LangChain Runnable、Document 或自訂 Function／Class。不能把框架內部物件直接當作對外持久化格式。
- Config、業務輸入與執行 Context 分離；Python Class／Type Hint 不會自動提供完整 Runtime Validation。
- 下文的「MVP」是建議範圍；後續方法是候選，尚未承諾全部開發。

## 2. 共用契約

### 2.1 呼叫與回應

```text
Module(config).run(input, context) -> ModuleResult[output]
```

此形式表示邏輯契約；可實作為 async method，或以 Adapter 包裝同步 function。每個模組宣告支援的 sync／async／batch／streaming 能力，不預設全部支援。

| 結構 | 必填欄位 | 選填欄位／規則 |
|---|---|---|
| ModuleConfig | contract_version、module_id、implementation_version、method、parameters | provider_ref、secret_refs；只保存憑證引用 |
| RunContext | run_id、trace_id、workspace_id、group_id、rag_system_id、config_revision、deadline_at | attempt、idempotency_key；由平台注入可信 auth_scope，不接受使用者自行聲明 ACL |
| ModuleResult[T] | status、data、errors、warnings、metrics | status = succeeded / partial / failed；failed 時 data=null |
| ModuleError | code、message、retryable | item_id、details；不能含 Secret 或完整敏感內容 |
| ExecutionMetrics | duration_ms、input_count、output_count | token_usage、provider_request_id；不適用欄位可省略 |

**部分失敗**：Ingestion 批次允許 partial；成功項目可進入下一步，失敗項目必須有 item_id。所有輸入須可對應到成功、失敗或明確 skipped 結果，不可默默丟棄。Inference 的 optional fallback 需寫入 warnings，不能把 provider error 假裝成「沒有搜尋結果」。

**重試**：由 Execution Policy 統一管理。只有暫時性錯誤與可安全重試的操作才重試；Indexing、Import checkpoint 等具副作用步驟須使用冪等策略。

### 2.2 共用資料物件

以下使用結構化記法；`?` 表示選填，`[]` 表示清單，`JSON` 表示可 JSON 序列化資料。正式實作應轉成具版本的 Pydantic Models／JSON Schema。

| 物件 | 欄位與語意 |
|---|---|
| ArtifactRef | `uri: str, media_type: str, checksum: str, size_bytes: int`；由平台解析的物件儲存引用，不在跨程序 payload 傳遞巨型 bytes |
| SourceAsset | `document_id: str, source_revision: str, source_uri: str, content: ArtifactRef, metadata: JSON, access_policy_ref: str` |
| Location | `page_number?: int, section_path?: str[], block_id?: str, char_start?: int, char_end?: int`；頁碼從 1 起；字元 offset 為指定 block 內 Unicode code point、0-based 半開區間 |
| DocumentBlock | `block_id: str, kind: text/table/heading, text: str, location: Location`；表格先標準化成可讀文字，保留 kind |
| ParsedDocument | `document_id, source_revision, blocks: DocumentBlock[], metadata, access_policy_ref, parser_version` |
| Chunk | `chunk_id, document_id, source_revision, text, locations: Location[], metadata, access_policy_ref, chunking_signature, parent_id?: str` |
| EmbeddingProfile | `profile_id, provider_ref, model_id, model_version, vector_kind, dimension?, document_encoding, query_encoding, normalization`；encoding 包含各自的 prefix/task 設定 |
| Vector | Dense：`values: float[]`；Sparse：`indices: int[], values: float[]`；以 kind 區分，不混用 |
| VectorSet | `profile_id, items: [{chunk_id, vector: Vector}]`；可有多組 Profile，MVP 僅一組 Dense |
| IndexBinding | `backend_ref, index_id, generation_id, schema_version, capabilities: str[], embedding_profiles: EmbeddingProfile[]` |
| SearchQuery | `query_id, text, kind: original/rewrite/expanded/hypothetical, weight?: float` |
| SearchHit | `chunk: Chunk, rank: int, score?: float, score_kind: str, matched_query_ids: str[]` |
| ChatMessage | `role: user/assistant, content: str`；MVP 歷史不接受使用者注入 system role |
| Citation | `citation_id, chunk_id, document_id, source_revision, locations: Location[]` |

補充約束：

1. `document_id` 在同一 System 的同一邏輯來源上穩定；內容版本另以 `source_revision` 區分。來源重命名如何辨識同一文件，由 Connector 規則決定。
2. `chunk_id` 依來源版本、Chunking Signature 與位置／序號確定性產生；換 Chunking 後不能沿用舊 Chunk 的標註 ID。
3. `metadata` 只放 JSON 值；平台保留身份、來源與權限欄位，自訂程式不能覆寫以提升存取權限。
4. `generation_id` 指平台管理的索引資料版本；建立後是否不可變由後端與平台實作保證，不能把可變 alias 稱為 Snapshot。沒有穩定資料版本時，Evaluation 必須標記不可完全重現。
5. Search score 不是機率。BM25、cosine、RRF、Rerank score 不可假設能直接比較；rank 從 1 起。
6. 契約版本以 major/minor 管理；MVP 可採未知欄位拒絕、明確 migration，避免悄悄吞掉拼錯欄位。

## 3. Ingestion 模組

### 3.1 Data Import

**目的**：取得原始資料及來源資訊，產出可供 Parsing 讀取的 SourceAsset。此層不負責 PDF/OCR 解析。

| 項目 | 規格 |
|---|---|
| MVP 方法 | File Upload |
| 後續方法 | Object Storage、HTTP/Website、Database Query |
| Config | connector、allowed_formats、max_file_bytes；Connector 可另有 source_path、query、secret_ref、incremental_mode |
| Input | `ImportInput {source_spec: SourceSpec, cursor?: str, limit: int}` |
| Output | `ImportOutput {assets: SourceAsset[], deletions: [{document_id, source_revision?}], next_cursor?: str, has_more: bool}` |
| SourceSpec | tagged union：`upload {artifact_refs[]}`／`object_storage {location_ref,prefix}`／`http {url}`／`database {connection_ref,query_ref}`；MVP 只接受 upload |
| 驗證 | 來源授權、格式與大小；資源 URI 必須經平台授權解析；空批次可成功，但要明確 has_more |

Cursor 為 opaque token。資料「已讀取」不等於「已索引」，可恢復的 committed checkpoint 必須等下游成功再推進。刪除事件由 orchestrator 直接送 Indexing，不送 Parsing／Chunking／Embedding。MVP 不提供完整來源同步刪除；後續 Connector 必須能區分刪除與暫時讀不到。

### 3.2 Parsing

**目的**：將檔案轉成標準 DocumentBlock，保留可追溯的頁碼、段落與表格來源。

| 項目 | 規格 |
|---|---|
| MVP 方法 | Native Text Extraction：PDF 文字層、TXT、Markdown；具體格式依已註冊 Parser 能力 |
| 後續方法 | OCR、Layout-aware Parsing；DOCX 等格式以新增 Adapter 支援 |
| Config | parser_id、format_policy、ocr_mode、language、preserve_tables、preserve_headings |
| Input | `ParsingInput {assets: SourceAsset[]}` |
| Output | `ParsingOutput {documents: ParsedDocument[]}` |
| 驗證 | Parser 接受的 MIME type；Document ID／source_revision／ACL 必須保留 |

掃描 PDF 在未開啟 OCR 時應回傳 `OCR_REQUIRED` 或可辨識的 empty-text 錯誤，不可將「解析成功但沒有文字」當作可檢索文件。Parser 不提供標題結構時，不能宣告適用 Header-aware Chunking。

### 3.3 Chunking

**目的**：將 ParsedDocument 轉成檢索單位，保留來源位置與 Metadata。

| 項目 | 規格 |
|---|---|
| MVP 方法 | Recursive、Header-aware（需 Parser 輸出標題結構） |
| 後續方法 | Fixed-size、Sentence-based、Semantic、Parent–Child |
| Config | size、overlap、length_unit: characters/tokens、tokenizer_ref（tokens 時必要）、separators、header_levels |
| Input | `ChunkingInput {documents: ParsedDocument[]}` |
| Output | `ChunkingOutput {chunks: Chunk[], parents?: Chunk[]}` |
| 驗證 | size > 0；0 ≤ overlap < size；輸出非空文字；來源與權限不可丟失 |

`size` 的單位必須明示；不同 tokenizer 的 Token 數不保證一致。Parent–Child 為後續能力：children 的 parent_id 須指向 parents；父文件需另外保存供 Retrieval 使用，MVP 不使用此欄位。Semantic Chunking 若呼叫模型也須宣告依賴與成本。

### 3.4 Embedding

**目的**：將 Chunk 編碼成 VectorSet，並綁定可重現的 EmbeddingProfile。

| 項目 | 規格 |
|---|---|
| MVP 方法 | Dense Embedding |
| 後續方法 | Sparse Embedding、Dense＋Sparse；Multi-vector 暫不納入 v0.1 Vector 契約 |
| Config | provider_ref、model_id/version、dimension、encoding、normalization、batch_size、input_overflow_policy |
| Input | `EmbeddingInput {chunks: Chunk[]}` |
| Output | `EmbeddingOutput {chunks: Chunk[], profiles: EmbeddingProfile[], vector_sets: VectorSet[]}` |
| 驗證 | Vector 與 chunk_id 一一對應；Dense 維度一致且值有限；Sparse indices 非負、不重複且與 values 等長；模型輸入長度符合限制 |

超長輸入預設回報錯誤，不能默默截斷；若允許 truncate，須在 Config 明示並記 warning。Output 僅含成功編碼的 chunks，失敗以 ModuleError.item_id 記錄。

純 BM25 流程由 orchestrator 略過此模組，直接傳遞 chunks，Indexing 的 profiles／vector_sets 為空。Hybrid 的全文側若由 Elasticsearch BM25 提供，不需另跑 Sparse Embedding。

### 3.5 Indexing

**目的**：以固定 Schema 寫入 Chunk、Vector 與 Metadata，回報寫入與可搜尋狀態。

| 項目 | 規格 |
|---|---|
| MVP 方法 | Dense、Full-text、Hybrid；先整合 Elasticsearch 一個 Backend |
| 後續方法 | 新增 Backend；父子文件儲存；Multi-vector 需新契約 |
| Config | backend_ref、index_schema、similarity、write_mode: upsert/replace_document、refresh_policy |
| Input | `IndexingInput {target: IndexBinding, chunks: Chunk[], profiles: EmbeddingProfile[], vector_sets: VectorSet[], deletions: [{document_id,source_revision?}]}` |
| Output | `IndexingOutput {binding: IndexBinding, results: [{item_id,status: upserted/deleted/skipped/failed}], write_acknowledged: bool, searchable: bool}` |
| 驗證 | 欄位 Mapping、向量維度與 Profile 相容；完整保留來源與 ACL；寫入不跨 System |

- Index 建立／Schema provisioning 屬於 Runtime Controller；本模組取得已準備好的 target，不能以任意使用者字串建立未授權索引。
- `write_acknowledged` 不等於 `searchable`；依 refresh 狀態回報，平台不可過早顯示可查詢。
- `replace_document` 需清除舊 revision 的殘留 Chunks；應以完整文件成功寫入為條件切換可見版本，不能遇到半批失敗就刪掉舊資料。
- Upsert ID 與 idempotency_key 支援安全重試；同一 document 的 upsert/delete 衝突與事件順序須由版本檢查處理。

## 4. Inference 模組

### 4.1 Query Transformation

**目的**：將使用者問題轉成適合檢索的 Query，同時保留原始問題供回答。

| 項目 | 規格 |
|---|---|
| MVP 方法 | None、Query Rewrite |
| 後續方法 | History-aware Rewrite、Multi-query、HyDE、Query Decomposition |
| Config | method、model_ref、prompt_version、max_queries、use_history |
| Input | `QueryTransformInput {question: str, history: ChatMessage[]}` |
| Output | `QueryTransformOutput {original_question: str, queries: SearchQuery[]}` |
| 驗證 | question 非空；至少一個有效 Query；數量不超過 max_queries；original_question 不可被改寫 |

None 必須回傳一個原始 Query。HyDE 的 hypothetical text 僅作為檢索輸入，不是來源證據，不能直接當成 Generation 的 retrieved context。分解問題若需要逐步求解或工具調用，屬於後續編排設計，不由此契約承諾。

### 4.2 Retrieval

**目的**：依 Query 搜尋 Index，回傳去重且帶來源的候選 Chunks。

| 項目 | 規格 |
|---|---|
| MVP 方法 | Dense、BM25、Hybrid（先提供 RRF 融合） |
| 後續方法 | MMR、多 Query 合併、Parent–Child Retrieval、加權融合 |
| Config | candidate_top_k、per_query_top_k、fusion、search_parameters；Query Embedding 由 IndexBinding Profile 繼承 |
| Input | `RetrievalInput {query: QueryTransformOutput, index: IndexBinding, filter?: MetadataFilter}` |
| Output | `RetrievalOutput {original_question: str, hits: SearchHit[], index: IndexBinding}` |
| 驗證 | Retrieval 能力與 Index 相容；Filter 欄位與運算子經 Schema 驗證；Query Embedding Profile 必須匹配 |

`MetadataFilter` 為 allowlist AST：`condition {field,op,value}`，或 `and/or {children[]}`；MVP 可先只支援 eq/in/range，不接受任意後端 query DSL。

- 平台將使用者 filter 與 RunContext 的強制授權條件以 AND 合併。系統隔離、ACL 不由自訂 Query 或 Plugin 決定；回傳前再次確認輸出授權。
- Dense Query 編碼是本模組內的步驟，重用 EmbeddingProfile；Query／Document 的 prefix/task 可以不同，但必須是該 Profile 定義的配對。
- Hybrid 的兩路候選先融合，再截取 candidate_top_k；其範圍是最終候選上限，不是兩路數量相加。
- 多 Query 需保留 matched_query_ids、去重並統一排序；v0.1 MVP 可只接受單 Query，超過時回報不支援，不能忽略其他 Query。
- `hits=[]` 是合法的成功結果；Index／Provider 故障則是 failed，兩者不同。
- Backend 原始分數可留在追蹤資訊；SearchHit.score_kind 明確標示最終排序分數的種類。

### 4.3 Rerank

**目的**：按原始問題重排 Retrieval 候選，挑出要交給 Generation 的內容。

| 項目 | 規格 |
|---|---|
| MVP 方法 | None、Cross-Encoder |
| 後續方法 | LLM Rerank、自訂排序 |
| Config | model_ref、top_n、batch_size、pair_token_limit |
| Input | `RerankInput {original_question: str, hits: SearchHit[]}` |
| Output | `RerankOutput {original_question: str, hits: SearchHit[], applied: bool}` |
| 驗證 | 不可發明新的 chunk_id 或修改文件內容／ACL；輸出為候選子集；rank 重新編號 |

None 時 applied=false、原樣傳遞全部 hits，top_n 停用且不參與執行。啟用時要求 top_n ≤ candidate_top_k；實際只取 min(top_n, hits 數量)，零筆候選直接成功回傳空清單。不要因搜尋結果少於配置上限而判定錯誤。Rerank score 與原 Retrieval score 分開保存於 Trace，不覆蓋後失去可追溯性。

### 4.4 Generation

**目的**：組裝有限的來源 Context，產生回答與引用。

| 項目 | 規格 |
|---|---|
| MVP 方法 | Context-grounded Generation |
| 後續方法 | Structured Output；多階段摘要／生成另行設計 |
| Config | model_ref、prompt_version、temperature、max_output_tokens、context_budget、stream、no_context_policy |
| Input | `GenerationInput {question: str, history: ChatMessage[], contexts: SearchHit[]}` |
| Output | `GenerationOutput {answer: str, citations: Citation[], used_chunk_ids: str[], finish_reason: str, usage: TokenUsage, abstained: bool, structured_output?: JSON}` |
| 驗證 | Context＋History＋Prompt＋Question＋輸出預留符合模型預算；引用 ID 必須出現在實際供模型使用的 Context |

Context Assembly 先放在 Generation 內：來源標記、去重、依排名截取與預算控制；不增加一個 UI 模組。`used_chunk_ids` 表示實際送入 Prompt 的內容，不代表模型必然使用或支持每個主張。Citation ID 有效不等於語意正確，引用品質需另行評估。

MVP `no_context_policy=abstain`：無 Context 時回傳清楚的無足夠資料訊息、citations=[]、abstained=true；不是系統錯誤。使用者問題仍採原始 question，而非 Rewrite 後的查詢。

Streaming 是獨立事件契約：

```text
GenerationEvent = {run_id, seq, type: delta/completed/failed, payload}
```

delta 只含文字增量；completed 含完整 ModuleResult[GenerationOutput]；failed 含標準錯誤。每次串流只有一個 terminal event，completed 不能在 failed 後再出現。增量中的引用屬 provisional，以最終完成結果為準。MVP 可先只做非 Streaming，不宣告未支援能力。

`TokenUsage {input_tokens?: int, output_tokens?: int, total_tokens?: int}`：Provider 不提供時為 null，不能填 0 假裝沒有用量。

## 5. Evaluation 模組

**目的**：在可追溯的 Config 與 Index 版本上跑 QA Dataset，評估 Retrieval、回答與操作指標。

| 項目 | 規格 |
|---|---|
| MVP 方法 | Deterministic Retrieval Metrics、LLM-as-a-Judge、Operational Metrics |
| 後續方法 | Custom Evaluator、Baseline Comparison；進階自動 Gate 不是目前必要 UI |
| Config | mode: retrieval_only/end_to_end、metrics、judge_model_ref/version、rubric_version、concurrency |
| Input | `EvaluationInput {dataset: DatasetRef, target: EvaluationTarget}` |
| Output | `EvaluationOutput {evaluation_run_id, binding: EvaluationTarget, results_ref: ArtifactRef, summary: MetricSummary[], total, succeeded, failed, skipped}` |
| DatasetRef | `dataset_id, version, artifact: ArtifactRef` |
| EvaluationTarget | `rag_system_id, config_revision, index: IndexBinding, engine_image_digest, plugin_versions, judge_model_version?` |
| QARecord | `case_id, question, expected_answer?, relevant_document_ids?: str[], relevant_chunk_ids?: str[], reference_index_generation?: str, history?: ChatMessage[], metadata_filter?: MetadataFilter` |

逐題結果記錄：`case_id, status, generated_answer?, retrieved_ids, context_chunk_ids, scores[], errors[], trace_id`。

`MetricResult {metric_id, value: float|null, status: scored/skipped/failed, reason?, unit}`；`MetricSummary {metric_id, aggregate?, aggregation, evaluated_count, skipped_count, failed_count, unit}`。缺少必要標註時預設 preflight 拒絕該指標；若使用者明確允許跳過，須標示 skipped 與原因，不得把缺資料當 0 分。

| 指標 | 所需輸入 | 語意 |
|---|---|---|
| Recall@K | relevant IDs＋前 K 個去重 retrieved IDs | 找回多少相關項目；先固定 document 或 chunk 評估層級 |
| MRR | relevant IDs＋完整候選排序（或明示 MRR@K） | 第一個相關結果的 reciprocal rank；無命中為 0 |
| Answer Correctness | question＋expected_answer＋answer＋評分規則 | 通常由 Judge 評分，需記錄模型與 rubric |
| Faithfulness | answer＋實際供 Generation 使用的 contexts | 回答是否受所提供內容支持，不等同真實世界正確性 |
| Latency／Token Usage／Error Rate | 每題執行記錄 | 不可把失敗請求排除後仍聲稱是全量成功率 |

- 先固定 Retrieval 評估點為 Rerank 前；若測 Rerank 後，另用不同 metric_id，不能混在同一結果。
- Document-level 評估先將多個 Chunks 聚合成唯一 document_id，再套用 K，並明示此定義。
- relevant IDs 為空與缺失不同；無答案題的 Retrieval Recall 預設不適用，另評估 abstention，不能除以零。
- Config、Index、Dataset／Judge 版本都需綁定；修改 Chunking 後須重建 Chunk 級標註或明確 migration。
- Evaluation Runner 是後端 Job；提供 Job ID／狀態輪詢屬平台 Job API，不是每個模組都實作一個 Queue。

## 6. 各模組 I/O 接線摘要

| 來源 | 目的 | 連接方式 |
|---|---|---|
| Import.assets | Parsing.assets | 原樣傳遞 SourceAsset |
| Parsing.documents | Chunking.documents | 保留結構、版本與來源 |
| Chunking.chunks | Embedding.chunks | BM25 模式可繞過 |
| Embedding.chunks/profiles/vector_sets | Indexing 對應欄位 | target 由 Controller 注入；deletions 由 Import 旁路傳入 |
| Query Transformation.output | Retrieval.query | index 由 Runtime 注入；filter 經平台授權合併 |
| Retrieval.original_question/hits | Rerank 對應欄位 | index binding 留在 Run Trace |
| Rerank.original_question/hits | Generation.question/contexts | history 由原始請求保留並注入 |
| Dataset＋EvaluationTarget | Evaluation | Runner 呼叫上述 Inference 契約並收集 Trace |

平台 Compiler 必須負責欄位映射及旁路資訊傳遞；不是單純把上一個模組的完整 JSON 塞到下一個模組。

## 7. 相依規則與 UI 卡控

| 規則 | UI | 後端 |
|---|---|---|
| Dense-only Index → Retrieval | BM25／Hybrid 顯示但停用，附原因 | capabilities 驗證；不是按資料庫品牌一刀切 |
| Query Embedding → Index Profile | Model／Dimension 唯讀繼承 | 驗證完整 Profile，包括 encoding／normalization |
| BM25 → Dense Embedding | 顯示「不使用」，停用相關設定 | 跳過向量步驟，不載入不必要模型 |
| Rerank=None → Top-N | 保留但停用 | 從有效執行 Config 排除 |
| Top-N > candidate_top_k | 顯示上限與錯誤、阻止建立 | 拒絕非法 Config；不限制實際候選必須滿 K |
| 非 Hybrid → Fusion／Dense Weight | 顯示但停用 | 不傳無效參數給 Backend |
| Header-aware → Parser headings | 缺能力則停用或標示不相容 | 檢查 requires/provides，執行時驗證結構 |
| Embedding dim → Index dim | Index 繼承或提示重建 | 不允許混入不相容向量 |
| Retrieval Metric → Dataset | 顯示缺少標註 | preflight 拒絕或明確 skipped |

上游改動造成既有選項失效：保留原選擇、標示原因、停用 Create，直到使用者修正。不能悄悄切換方法。方法未啟用的參數可保留在 UI 草稿，但不得影響有效 Config 的驗證、Hash 或執行。

變更 Parsing／Chunking／Embedding／Index Schema 通常需重新 Ingestion；只改 Top-K、Rerank、Prompt 通常不用重建 Index，但仍需重新評估。重建成本由 Dependency Validator 回報，不只靠 UI 提醒。

## 8. Custom Python 與技術分工

### 8.1 Module Registry

每個已註冊模組需提供：

```yaml
module_id: company.chunking.recursive
implementation_version: 1.0.0
contract_version: 1.0
module_type: chunking
entry_point: company_rag.chunking:RecursiveChunker
input_schema: ChunkingInput@1
output_schema: ChunkingOutput@1
config_schema: RecursiveChunkingConfig@1
requires: [document.text]
provides: [chunk.text, chunk.provenance]
supports: {async: true, batch: true, streaming: false}
```

上述是自訂 manifest 示例；能力宣告須配合 Contract Test 驗證。平台註冊資料另保存 artifact digest、dependency lock、runtime compatibility 與外部服務需求。

### 8.2 客製化邊界

- 先開放 Chunking、Query Transformation、Rerank、Evaluation；其他模組優先經平台註冊 Plugin。
- 使用者可提供 Function 或 Class，不要求與 LangChain 類別繼承綁死。
- Adapter 的順序為：Config 驗證 → Input Runtime Validation → 執行政策 → 自訂邏輯 → Output Runtime Validation → provenance／ACL／跨欄位檢查。
- Pydantic 結構驗證之外，還需檢查「Chunk 是否保留來源」、「Rerank 是否只回傳候選子集」等語意規則。
- 任意使用者程式不得直接在共用 API Process 中 exec；隔離執行與受控資料／Secret 存取屬正式實作前置條件。
- Config 固定 Plugin Version；新增程式與依賴時建置版本化 Runtime Image。部署 YAML 鎖定 Image Digest，不能只匯出 Class 名稱而漏掉實作。

### 8.3 Framework／Platform 分工

| 層 | 建議責任 |
|---|---|
| LangChain | 可重用模型、Retriever、Loader Adapter，以及線性 Runnable 組合 |
| LangGraph | 有必要時處理分支、狀態與 checkpoint；不要求每個模組獨立建 Graph |
| Pydantic | Config／Input／Output 的顯式 Runtime Validation |
| 自建 Platform Engine | Registry、Compiler、Compatibility、Job Lifecycle、Execution Policy、版本及隔離 |
| Observability | Langfuse＋OpenTelemetry 為候選方向，尚未定案；先定義一致 trace_id/module_id/run_id |

Queue、重試、DLQ、冪等 Indexing 與恢復語意不能只靠框架名稱保證。MVP 先固定流程；使用者 UI 維持 Group／RAG System 卡片與操作彈窗，不把這些後端機制全部暴露成頁面。

## 9. 第一版建議組合與待決事項

### MVP 建議

File Upload → Native Text Parsing → Recursive／Header-aware → Dense Embedding（BM25 可略過）→ Elasticsearch Dense／Full-text／Hybrid → None／Query Rewrite → Dense／BM25／Hybrid RRF → None／Cross-Encoder → Context-grounded Generation。

Evaluation 提供標註 ID 的 Recall@K／MRR、Judge 型 Answer Correctness／Faithfulness 與基本執行指標。實際可啟用指標由 Dataset／Trace 輸入決定。

### 待決事項

1. 首批檔案格式與 Parser；是否第一期就納入 OCR。
2. 第一組 Embedding／Rerank／Generation 模型及服務接口。
3. Chunk 長度單位、Tokenizer，以及 Metadata／ACL 欄位清單。
4. Index version／generation 的儲存與切換方式，來源更新是否採完整文件替換。
5. 自訂程式是只接受核可套件，還是提供 UI 上傳與隔離試跑。
6. Streaming、增量同步與 Baseline Comparison 的優先序。

## 10. 參考與文件關係

本文件補充最新模組設計；既有 03_architecture_proposal.md 為較早的整體提案，UI／框架方向有差異時以本文件和已更新的 UI 說明為討論基準。這不表示所有候選方法已通過選型或已實作。

- LangChain component architecture：https://docs.langchain.com/oss/python/langchain/component-architecture
- LangChain Embedding integrations：https://docs.langchain.com/oss/python/integrations/embeddings
- LangChain ParentDocumentRetriever：https://reference.langchain.com/python/langchain-classic/retrievers/parent_document_retriever/ParentDocumentRetriever
- Ragas Metrics：https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/
- Qdrant Hybrid Queries：https://qdrant.tech/documentation/search/hybrid-queries/

這些資料作方法與整合參考；本文的 Object、ModuleResult、Registry 與 API 字段均為平台自己的提案。
