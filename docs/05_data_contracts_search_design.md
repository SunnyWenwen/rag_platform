# RAG Builder — 共用資料模型與 Config 規格

> 文件集 v0.14 · 2026-10-15 · 開發規格草案
>
> 本文是資料形狀及設定規則的權威位置。已確認的語意保留；新增的程式型別、完整 Config 拼字與預設值為建議草案，待 Q-002 核定後才凍結。YAML 範例用於討論與驗收設計，目前沒有 Engine 可直接執行。

## 1. 範圍與讀法

- 名詞意義與元件關係以 [03 §3](../03_architecture_proposal.md#terminology) 為準；本文負責資料結構、欄位、版本規則及範例，不另定同名概念。
- 模組如何執行見 [04](04_module_methods_io_contracts.md)，UI 見 [06](06_ui_development_spec.md)，HTTP 包裝／儲存見 [07](07_backend_runtime_integration.md)。
- 本文統一 ParsedDocument、Chunk、SearchHit、Config 及 ModuleResult，避免各模組重複定義。
- 物件形狀、Contract 版本與細節待 [Q-002](08_implementation_plan.md#q-002) 核定；已確認的五／六個頂層 key 不因此退回舊版。
- `?` 表示可省略，不自動表示可為 null；`JSON` 必須可序列化，數值不可為 NaN／Infinity。正式 required／nullable／additionalProperties 須由 Schema 定義。

<a id="identity-versions"></a>

## 2. 識別、版本與作用域

版本概念的正式定義見 [03 §3.4](../03_architecture_proposal.md#version-terms)。下表是對應的欄位用途與未決實作政策；其中 source_revision 指匯入 RAG 的來源文件內容，不是本 repository 的 Markdown 規格版本。

| 欄位／概念 | 語意 | 狀態 |
|---|---|---|
| workspace_id／system_id | Workspace → System；System 的邏輯識別跨環境不因部署設定不同而另改 Config，授權由可信 Context 決定 | 階層／邏輯方向已確認；格式與部署識別待決 |
| document_id | 同一 System 中邏輯文件的穩定識別，不能用 Chunk ID 取代 | 已確認；產生演算法 Q-007 |
| source_revision | 文件內容版本，與 Config Revision 不同 | 已確認；省略時的生成／比較 Q-007 |
| chunk_id | 由文件、來源版本、切分有效設定與位置／序號產生 | 已確認方向；規範化／Hash Q-007 |
| config_revision | 平台保存的設定版本 | 已確認；草稿／生效語意 Q-015 |
| index_generation | 可追蹤的索引資料版本，不能把可變 alias 當 immutable snapshot | 已確認方向；切換 Q-010／Q-015 |
| contract_version | 資料／Config 契約版本 | 建議；遷移 Q-002 |
| run_id／request_id／trace_id | 批次工作、單次請求及追蹤識別 | 已確認方向；線上包裝 Q-019 |

CSV 每列是邏輯文件。跨批更新需映射穩定鍵；Prototype 的批次自動 ID 不能宣稱可跨次穩定。檔案拆為多份文件時保留來源資產關聯，不能讓所有列沿用同一 document_id。

### 2.1 版本變更範例與規則

以下用同一 System 的兩份來源文件 A／B，示範 03 定義的三種業務版本如何分別變動：

| 成功完成的變更 | 文件 A／B | Config Revision | 索引資料版本 |
|---|---|---|---|
| 初次匯入 | A:v1、B:v1 | C1 | I1 |
| A 原文修改並成功更新索引 | A:v2、B:v1 | C1 | I2 |
| 原文不變，改 Chunk Size 並重建 | A:v2、B:v1 | C2 | I3 |
| 只改 Generation Prompt | A:v2、B:v1 | C3 | 仍可沿用 I3 |

以上 I1～I3 是說明概念的識別，不是已選定快照實作。即使 source_revision 不變，重切／重新 Embedding／索引重建也可能形成新索引資料版本；新文件尚未成功發布時，不能先把現有索引說成已含新版內容。兩者不一對一。

不同環境的資料可不同，故相同 Config 不保證 index_generation／文件集合相同。是否保留實體不可變快照、何時生成 ID 與原子切換仍由 Q-010／Q-015 核定；此處不新增已完成的版本管理承諾。

### 2.2 collection 命名（已確認方向）

Builder 由 Workspace＋RAG System 名稱自動產生邏輯 collection，使用者不用手填。既有實作附穩定 System ID，避免同名及正規化碰撞；建立後改顯示名稱不重命名既有目標。UI 的邏輯名稱唯讀；各環境的 DB／實體索引目標由部署綁定及 Adapter 管理，不因實體目標不同修改處理 Config。正規化演算法、長度與匯入既有集合的權限規則仍屬 Q-007／Q-019，不重開「是否自動命名」的方向。直接 Engine 則使用 Config／可信 Binding 中明確的集合，不依賴 Builder 才可運作。

## 3. Document Schema

固定外層不可自訂。每個 System 宣告 fields／metadata 的內部欄位：

| 屬性 | 規則 |
|---|---|
| name | 容器內非空、唯一；不可占用平台保留欄位 |
| type | 現有方向為 string／number／boolean／array；array 元素型別及巢狀物件 Q-002 |
| required | Input 欄位在接收時檢查；Parser 來源在 Parsing 完成後檢查 |
| source | input／parser；不能要求呼叫者偽造 Parser 產生的結構 |
| default | 必須符合型別；缺值、null、空字串的區別需核定 |
| unknown_fields | Prototype 預設 reject；allow 可保留，後續選單仍只取已宣告欄位 |

預設只有必填 string 的 fields.text。主要切分欄位必填且為 string；Embedding／全文／Prompt 的文字用途只選型別相容欄位。第一版精確 Filter 只支援字串。Schema 名稱修改保留失效引用並阻止保存，不自動轉移到同名欄位。

**待決**：default 與 required 的順序、null／空白政策、缺少選填 Embedding 欄位如何處理、array 元素、保留名稱及 Schema migration，見 Q-002／Q-006。正式後端不得直接沿用 Prototype 的寬鬆 JavaScript 行為。

## 4. 共用業務資料

### 4.1 輸入 records 與 SourceAsset

JSON Ingestion 的每筆 Record 形狀已確認：

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {"text": "設備每月需清潔散熱孔。", "title": "保養規範"},
  "metadata": {"department": "manufacturing"}
}
```

JSON records 的 document_id 必填；source_revision 可由輸入提供，省略時的後端生成政策待定。metadata 可省略為空，實際允許欄位依 Schema。structure／vectors 由後續模組產生，不由 Record 提供。

SourceAsset 是 Import → Parsing 的內部物件，**建議**包含 asset_id、kind（file／records）、media_type、content_ref 或 record payload、source identity、已驗證 metadata。ArtifactRef 建議包含 uri、media_type、checksum、size_bytes；URI 由 Runtime 授權解析，不接受任意檔案路徑／內網 URL。

檔案 manifest、實際位元組／引用的傳遞策略與資產保存見 Q-005／Q-007／Q-016；不能因使用 ArtifactRef 就強制獨立 Runtime 依賴 Builder Object Storage。

### 4.2 ParsedDocument：五個固定頂層 key

| Key | 型別 | 語意 |
|---|---|---|
| document_id | string | 邏輯文件 ID |
| source_revision | string | 來源內容版本 |
| fields | object | 原文、標題、已有摘要等內容 |
| metadata | object | 來源、分類與平台保留資訊 |
| structure | object | 依 fields 欄位對應的區塊／頁碼／標題；可為 {} |

```json
{
  "document_id": "doc-001",
  "source_revision": "v1",
  "fields": {"text": "第一段。第二段。", "title": "維修手冊"},
  "metadata": {"department": "manufacturing"},
  "structure": {"text": {"blocks": [
    {"block_id": "b1", "kind": "text", "start": 0, "end": 4, "page_number": 1},
    {"block_id": "b2", "kind": "text", "start": 4, "end": 8, "page_number": 2}
  ]}}
}
```

start／end 為對應 fields 完整字串的 Unicode code point offset，0-based 半開區間；頁碼從 1 起。不能混用 block-local offset、UTF-8 bytes 或 JavaScript UTF-16 index。標題／表格 block 的完整 Schema 由 Q-005 核定。

### 4.3 Chunk：六個固定頂層 key

| Key | 責任 |
|---|---|
| chunk_id | Chunking 產生 |
| document_id、source_revision | 繼承文件 |
| fields | 主要欄位的切分片段＋指定複製欄位 |
| vectors | Chunking 為 {}；Embedding 寫入命名向量 |
| metadata | 必要保留資訊、指定 metadata、片段位置 |

```json
{
  "chunk_id": "doc-001:v1:c1",
  "document_id": "doc-001",
  "source_revision": "v1",
  "fields": {"text": "第一段。", "title": "維修手冊"},
  "vectors": {"text_vector": [0.12, 0.34, 0.56]},
  "metadata": {"department": "manufacturing", "locations": [
    {"field": "text", "start": 0, "end": 4, "page_number": 1, "block_id": "b1"}
  ]}
}
```

chunk_id 與三維向量僅示例。位置指原 ParsedDocument 欄位，不是 Chunk 內的重新起算位置。跨頁可有多個 locations。權限、來源、locations、切分及 Parser 版本應有平台保留區或 Run 記錄，精確命名 Q-006；不額外增加 Chunk 頂層 key。

Chunk 須自帶 Rerank／Generation 需要的內容，不強制回查 ParsedDocument。完整向量保存在索引／Chunk Store；檢索傳遞可令 vectors={}。欄位保存投影仍須保證所有下游內容可取得。

### 4.4 Embedding Profile 與 IndexBinding

| 物件 | 必要語意 |
|---|---|
| EmbeddingProfile | 模型／版本、維度、document/query encoding、normalization、Tokenizer／revision、向量種類；向量邏輯名稱對應來源欄位及 Profile |
| IndexBinding | System 範圍、後端／集合、資料版本、Mapping／Schema 版本、capabilities、每個向量的 Profile 綁定及可搜尋狀態 |

Profile 是 Query／Document 配對契約；不能只比較維度或模型顯示名稱。Profile／Binding 不在每筆 Chunk 重複。第一版多個命名 Dense 向量已確認；不同 Profile／模型同時配置的優先級見 Q-002／Q-003。

### 4.5 SearchQuery、SearchHit 與 Citation

以下欄位名為**建議草案**，需 Q-002 凍結：

| 物件 | 形狀 |
|---|---|
| SearchQuery | query_id、text、kind（original／rewrite／expanded）；非空文字 |
| SearchHit | chunk: Chunk、rank、score、score_kind、matched_query_ids；逐路分數與 rerank_score 存 Trace |
| Citation | citation_id、chunk_id、document_id、source_revision、locations |
| QueryResult | original_question、answer、citations、used_chunk_ids、finish_reason、usage、abstained |

rank 從 1 起；score 是相關性分數，不是機率。搜尋融合用 chunk_id 去重，文件分組用 document_id，兩者不同。Rerank score 不覆寫而遺失原 Retrieval score。

<a id="inference-state-draft"></a>

### 4.6 Inference 傳遞狀態與多路評分（討論草案）

2026-10-15 使用者要求先釐清 Inference 的物件／分數紀錄，再討論融合處理；融合可配置在合法步驟之後。以下是**提出討論的形狀，尚未核定**；欄位拼字、選填與 SDK 由 Q-002／Q-014 凍結。§4.5 的扁平 SearchHit 是既有單層基線，不能承擔所有逐路／逐階段語意。

**建議將 Chunk 內容與每次檢索／排序的分數分開。**同一 Chunk 可被多個 Query、多個 Index／欄位搜尋路徑命中，之後又取得 Fusion／Rerank 分數。Chunk 仍維持六個 key；可在同一 InferenceState 中共用內容，以多份 RankedList 表達各路及各階段結果。

| InferenceState 欄位 | 建議責任 |
|---|---|
| original_query | 原始 query_id／文字；Rewrite 不覆寫 |
| search_queries | 本次實際送搜尋的 Query 清單，含 query_id／文字；由 include_original 控制是否納入原始問題 |
| chunks | chunk_id → 既有 Chunk；內容共用一份，不把分數塞入 fields／metadata |
| rankings | 多份具名 RankedList，包含原始檢索、Fusion、Rerank 結果 |
| active_ranking_ids | 下一步使用哪些排序清單；既有分數仍可追蹤，不靠覆寫單一 current_score 表達 |

Run／System／授權及 Deadline 仍由 RunContext 提供，與業務狀態分開。此為 Engine 內部傳遞草案，沒有要求 HTTP Query 回傳全部狀態；診斷曝光及保存另由 Q-016／Q-019 決定。

| RankedList 欄位 | 建議責任 |
|---|---|
| ranking_id | 本次結果的唯一識別，供下游與來源關聯 |
| stage | retrieval／fusion／rerank 等產生結果的階段；具體枚舉待決 |
| search_query_ids | 此結果涵蓋哪些搜尋 Query；跨 Query 融合可有多筆 |
| route_id、index_ref、field_path | Retrieval 的路徑／邏輯索引綁定／欄位；Fusion 等衍生結果可由輸入關係追溯，不偽造單一 Index |
| input_ranking_ids | 本次處理使用哪些先前結果；原始 Retrieval 為空清單 |
| operation | 實際 method／parameters／model_ref 等操作資訊；用來追溯 Fusion 權重、RRF 常數或 Rerank 模型，精確結構待決 |
| score_kind、score_order | 分數語意與高低方向，例如 BM25、cosine、RRF、reranker score；不是機率或全域可比分數 |
| items | 有序的 chunk_id／score／rank；rank 以該份清單為範圍，從 1 起 |
| scoring_query_id（若適用） | Rerank 實際使用的問題，引用 original_query 或 search_queries；與結果涵蓋的搜尋 Query 區分 |

示例只有一個 Chunk，呈現它在三條原始路徑各有一筆分數；實際可有更多候選：

```json
{
  "original_query": {"query_id": "q0", "text": "設備多久需要清潔？"},
  "search_queries": [
    {"query_id": "q1", "text": "設備保養規範"},
    {"query_id": "q2", "text": "設備清潔週期"}
  ],
  "chunks": {
    "c1": {
      "chunk_id": "c1", "document_id": "manual-001", "source_revision": "v1",
      "fields": {"text": "設備每月需清潔散熱孔。"}, "vectors": {}, "metadata": {}
    }
  },
  "rankings": [
    {
      "ranking_id": "r1", "stage": "retrieval", "search_query_ids": ["q1"],
      "route_id": "text-bm25", "index_ref": "primary", "field_path": "fields.text",
      "input_ranking_ids": [], "score_kind": "bm25", "score_order": "higher_is_better",
      "items": [{"chunk_id": "c1", "score": 12.3, "rank": 1}]
    },
    {
      "ranking_id": "r2", "stage": "retrieval", "search_query_ids": ["q1"],
      "route_id": "text-dense", "index_ref": "primary", "field_path": "vectors.text_vector",
      "input_ranking_ids": [], "score_kind": "cosine_similarity", "score_order": "higher_is_better",
      "items": [{"chunk_id": "c1", "score": 0.84, "rank": 1}]
    },
    {
      "ranking_id": "r3", "stage": "retrieval", "search_query_ids": ["q2"],
      "route_id": "text-bm25", "index_ref": "primary", "field_path": "fields.text",
      "input_ranking_ids": [], "score_kind": "bm25", "score_order": "higher_is_better",
      "items": [{"chunk_id": "c1", "score": 9.7, "rank": 1}]
    }
  ],
  "active_ranking_ids": ["r1", "r2", "r3"]
}
```

範例 index_ref／route_id／欄位名稱為示意；能力由授權 IndexBinding／Config 提供，不允許請求藉此跨 System 搜尋。Query 向量依 Profile 產生，完整向量不必傳到 Rerank／Generation。這些 Inference 分數不新增至持久化 Chunk。

待討論的處理規則：

- Retrieval 建立每個 Query×搜尋路徑的清單；以 chunk_id 共用內容，不先把分數加總成唯一值。
- Fusion 選定輸入清單並建立新 RankedList，記錄方法／參數與 input_ranking_ids；原始分數不刪除。
- Rerank 同樣建立新清單及分數，記錄模型與實際評分問題；None 原樣傳遞，不偽造分數。
- 每份清單內的 rank 獨立；同 Chunk 出現在不同清單是合法的。Top-K／Top-N 截斷及保留政策需依階段配置，不能因內容共用就視為已做分數融合。
- 原始距離／分數需保留來源與方向；若轉成 relevance 或正規化，須記錄原值及轉換方法。不同 score_kind 的可比性、Sum Score 權重與轉換由 Q-011／Q-014 核定。
- Generation 需明確知道採用哪份排序／如何組 Context；多份 active 清單如何收斂、可插入融合的合法位置及預設仍待討論。

先確認這些資料責任，再核定實際 Score／RankedList 型別、融合步驟、分組與 API 診斷形狀；不由本草案選定預設融合方案。

## 5. 共用執行與錯誤物件

下列延續舊 04 的設計方向，正式欄位必填與狀態仍由 Q-002／Q-017 核定：

| 物件 | 建議欄位 |
|---|---|
| ModuleConfig | module_id、implementation_version、contract_version、method、parameters、服務引用 |
| RunContext | workspace_id、system_id、config_revision、run_id／request_id、trace_id、deadline、attempt、可信 auth_scope；環境／部署綁定另明確記錄 |
| ModuleResult[T] | status: succeeded／partial／failed，data、errors、warnings、metrics |
| ModuleError | code、module、message、retryable、item_id?、details? |
| ExecutionMetrics | duration_ms、input_count、output_count、token_usage?、provider_request_id? |

failed 時 data 為 null；partial 必須能對應成功／失敗／skipped 項目，不能默默少資料。哪些模組允許 partial 及如何提交資料仍受 Q-009 限制。HTTP 任務狀態不是 ModuleResult.status，見 07。

未知 Token Usage 為 null／省略，不填 0。Secret 與敏感原文不進錯誤／追蹤。使用者無權設定可信租戶／ACL Context。

<a id="config-spec"></a>

## 6. Config 結構與有效設定

### 6.1 Config 與部署設定的契約邊界

名詞定義及跨環境原則見 [03 §3.3](../03_architecture_proposal.md#config-terms)。正式 Schema 需將邏輯設定與環境部署綁定拆開：前者保存方法、參數、Schema／欄位／Prompt、模型語意及邏輯引用，後者解析服務端點、Secret 引用、DB／實體索引與資源設定。

同一 System、同一 Config Revision 的邏輯設定跨環境一致。若要改處理方法、模型／維度／Encoding 等語意，需建立新 Config Revision 並依影響重建，不用環境覆寫掩蓋邏輯差異。不同環境仍需檢查實際模型 Profile 相容性。

原型曾把服務 URL／Secret 引用與 Pipeline 放在同一物件，需明確 migration。具體型別與檔案包裝 Q-002 未凍結，但分離方向已確認。依 03 的正式用語，正式契約不新增 Blueprint 領域物件；舊匯出型別／檔名的遷移見 06。

### 6.2 草稿、有效 Config 與部署綁定

- UI Draft 保存基本／進階欄位及未啟用方法的草稿；不是所有欄位都參與執行。
- Effective Config 僅包含使用中的方法、參數、服務及欄位；AI 與手動入口共用編譯／驗證。
- 部署設定／環境覆寫只替換允許的連線／Secret／目標／運行資源，不修改 System 的邏輯 Config。
- 更換 Embedding 語意 Profile 不能當作純環境覆寫，必須重新 Embedding／Indexing。
- 使用相同服務的兩個模組引用同一 llm_ref；匯出只包含實際引用的服務。

邏輯 Config 根結構仍為**建議**：contract_version、document_schema、llms、pipelines.ingestion、pipelines.inference、execution。llms／Embedding 等只保留模型語意與穩定服務引用；URL／認證／資料目標由部署設定解析。System／Revision／IndexBinding 由 Context／可信綁定提供，HTTP／匯出包裝見 07。

### 6.3 模組設定詞彙

| 模組 | 已確認語意 | 本版建議 Config 欄位 |
|---|---|---|
| Import | files／records；CSV 先映射到 records | accepted_inputs、csv_mapping |
| Parsing | 格式路由、結構化 records 驗證 | routes |
| Chunking | Recursive／Header-aware；Token 計量 | method、split_field、copy_fields、metadata_fields、size、overlap、tokenizer、separators、keep_separator、header_levels |
| Embedding | fields → 命名 vectors | profile、mappings（source_field、output_name） |
| Indexing | 儲存、全文、向量、過濾分開；持久化模式跨環境固定 | backend、stored_fields、fulltext_fields、vector_fields、filter_fields、persistence、metric；persistence 屬邏輯 Config，collection 在部署 Binding |
| Query Transformation | None／Rewrite／Multi-query | method、llm_ref、prompt、count、include_original |
| Retrieval／Fusion Plan | 選已索引欄位、推導模式；可配置策略及合併時點 | fulltext_fields、vector_fields、per_route_k、top_k、filters、fusion；stages／scope／placement 具體 Schema 待 Q-014 |
| Rerank | None／DEV／Rerank API | method、service、content_fields、top_n |
| Generation | 兩層模板、共用 LLM | llm_ref、chunk_template、prompt、temperature、max_output_tokens、context_budget |

正式枚舉建議用 snake_case，UI 可顯示自然語言。Prototype 的 chunking.split、embedding.mappings[].source、indexing.filters、transform 等短名稱不自動視為正式 Schema；需明確 migration。統一使用完整路徑 fields.text／vectors.text_vector／metadata.department。上述拼字及預設值需 Q-002 核定，禁止同時接受未宣告別名而掩蓋錯誤。

### 6.4 參數與相依規則

| 條件 | 驗證 |
|---|---|
| Token Chunking | size 為正整數；0 ≤ overlap < size；Tokenizer 可取得；Header-aware 需 headings 能力 |
| Embedding mappings | 來源為有效文字欄位；output_name 唯一；有限值、維度與 Profile 相容 |
| Indexing | 搜尋欄位與上游一致；必要識別／來源／ACL 強制保留；下游使用欄位已保存 |
| Retrieval | 至少一路；每路及最終 K 為正整數；僅選已建立索引；Query Profile 由向量欄位繼承 |
| Fusion | 多 Query／多欄位需有明確計畫；基線為單層 Rerank 前，目標支援時點選擇；只使用已選策略有效參數 |
| Sum Score | 現有單層基線的預設；全文／向量權重預設各 1，有限非負，使用中至少一個大於 0；不自動正規化 |
| RRF | rank 從 1；k 預設 60 且為正整數；k 與 Top-K 不同 |
| Rerank | None 不執行且不使用 top_n；既有單層基線為 0 < top_n ≤ Retrieval top_k；逐 Query／多階段計畫的候選數與 K／N 關係待 Q-014，不沿用單一全域上限取代計畫驗證 |
| Templates | 只允許宣告變數；單次替換；未知／必要變數缺少阻止保存 |
| LLM | 引用有效；刪除使用中的服務不得默默換另一個 |

純 BM25 可跳過 Embedding，但 Chunking 仍需 Tokenizer。複製欄位長度可能大於 Chunk Size，Embedding 必須逐項檢查實際輸入。Tokenizer、模型極限及溢位政策見 Q-004。

**融合配置的目標要求已存在，細節尚待 Q-014**：必須能區分演算法、融合範圍（同 Query／跨 Query）與執行時點（Rerank 前／後）。可選兩層及預設計畫的精確支援範圍、route 型別、Top-K／Top-N 與分數語意需再核定；不能把全部合併為一個 fusion.method 後宣稱符合需求。`fusion.stages[]` 是先前助理提出的 Schema 候選，尚非已定欄位。

### 6.5 過濾條件

```json
[{"field":"metadata.department","operator":"eq","value":"manufacturing"}]
```

Indexing 宣告可過濾欄位；Retrieval 保存預設條件；Query API 可加本次條件。全部與後端強制授權 AND；in 清單內為任一值符合。第一版 eq 為非空字串，in 為非空、不重複字串清單。空條件清單不增加業務限制，不能取消 ACL。

所有 Query × 欄位路徑須在取 Top-K 前套用相同限制。缺值／null／多值精確語意與 Adapter 可用能力見 Q-013；不支援就拒絕配置。數值／日期／OR 群組列為後續。

## 7. 邏輯 Config 與部署設定範例（建議 Schema）

以下將 **既有單層融合基線的 Local Search／Memory 邏輯 Config** 與**部署設定**拆成兩個 YAML 範例。Config 不含環境 URL／認證或實體集合；部署設定按穩定引用綁定。具體 Schema 仍待 Q-002，融合時點需求待 Q-014；目前沒有 Engine 可執行這些草案。

```yaml
contract_version: 0.1-draft
document_schema:
  fields:
  - name: text
    type: string
    required: true
    source: input
  - name: title
    type: string
    required: false
    source: input
    default: ''
  metadata:
  - name: department
    type: string
    required: true
    source: input
  unknown_fields: reject
llms:
- id: llm-default
  name: Default LLM
  provider: openai_chat
  model_id: chat-model
  service_ref: llm-default
pipelines:
  ingestion:
    import:
      accepted_inputs:
      - records
      csv_mapping:
        id: document_id
        content: fields.text
        title: fields.title
        department: metadata.department
    parsing:
      routes:
        records: structured_records
    chunking:
      method: recursive
      split_field: fields.text
      copy_fields:
      - fields.title
      metadata_fields:
      - metadata.department
      size: 512
      overlap: 64
      tokenizer:
        id: tokenizer-example
        revision: pinned-example
      separators:
      - '


        '
      - '

        '
      - 。
      - ' '
      - ''
      keep_separator: true
    embedding:
      profile:
        profile_id: embedding-default
        service:
          provider: openai_embeddings
          model_id: embedding-model
          service_ref: embedding-default
        model_version: pinned-example
        dimension: 768
        vector_kind: dense
        document_encoding:
          prefix: ''
        query_encoding:
          prefix: ''
        normalization: l2
        tokenizer:
          id: tokenizer-example
          revision: pinned-example
        max_input_tokens: 8192
      batch_size: 16
      mappings:
      - source_field: fields.text
        output_name: text_vector
    indexing:
      backend: local_search
      persistence:
        mode: memory
      metric: cosine
      stored_fields:
      - fields.text
      - fields.title
      fulltext_fields:
      - fields.text
      vector_fields:
      - vectors.text_vector
      filter_fields:
      - metadata.department
  inference:
    query_transformation:
      method: none
    retrieval:
      fulltext_fields:
      - fields.text
      vector_fields:
      - vectors.text_vector
      per_route_k: 10
      top_k: 5
      filters: []
      fusion:
        method: sum_score
        score_weights:
          fulltext: 1
          vector: 1
    rerank:
      method: none
    generation:
      llm_ref: llm-default
      temperature: 0.2
      max_output_tokens: 1024
      context_budget: 4000
      chunk_template: '[{{citation_id}}] {{fields.title}}

        {{fields.text}}'
      prompt: '請根據參考資料回答並標示引用。資料不足時請明確說明。

        參考資料：

        {{context}}

        問題：{{query}}'
execution:
  request_timeout_seconds: 120
  max_attempts: 1
```

部署設定範例（同一 Config 可用不同環境的這份綁定）：

```yaml
environment: dev
config_revision: C1-example
service_bindings:
  llm-default:
    base_url: https://llm.example.invalid/v1
    auth:
      type: bearer
      secret_ref: llm-token/key
    timeout_seconds: 30
  embedding-default:
    base_url: https://embedding.example.invalid/v1
    auth:
      type: bearer
      secret_ref: embedding-token/key
    timeout_seconds: 30
index_binding:
  collection: workspace-manual-system-example
runtime:
  replicas: 1
  api_workers: 1
```

以上模型維度、Token 上限、Timeout、版本與名稱均為示例；部署 URL 用不可運作的 .invalid，Secret 只有引用。Engine 讀邏輯 Config，服務／Store resolver 依部署設定綁定。max_attempts=1 表示本例不自動重試，不宣稱重試政策已定案。

ES／Local Search 及 Local Search 的 Memory／MongoDB 持久化模式屬邏輯 Config。使用者於 2026-10-15 確認：DEV 用 Memory，FTEST／ENT 也用 Memory；不能以部署覆寫將同版 Config 的 Memory 改成 MongoDB。若要改模式，應修改 Config 並依資料準備／相容性政策處理；是否能重用既有 Chunk／vectors，而不重跑 Parsing／Embedding，仍由 Q-012／Q-015 核定。

各環境的 ES 連線／Secret／集合、MongoDB URI／DB／Collection 屬部署設定。改連線不代表資料已搬移；Memory 模式不要求 DB，各環境仍需準備自己的資料。上述 `indexing.persistence` 的欄位拼字與完整分支仍為 Q-002 Schema 草案，模式跨環境保持一致的語意已確認。DEV service_ref 與 Manifest 見 Q-012／Q-021。

## 8. Config 變更影響矩陣

| 有效變更 | 影響 |
|---|---|
| Document Schema、Import／Parsing／Chunking／Embedding／Indexing 的邏輯配置 | 新 Config Revision，標記需重新 Ingestion；中間產物重用另決 |
| 部署設定的 DB／實體索引目標 | Config Revision 不因此改變；更新部署綁定，目標需有相容資料或重新 Ingestion |
| 同 Profile 的模型服務 URL／Secret | 邏輯 Config 不變；驗證連線與實際模型相容性，不能把不相容模型當成純換 URL |
| Query Transformation、Retrieval、Rerank、Generation、被引用的 LLM | 不需重建；需重新測試／評估 |
| Indexing filter_fields | 需重建搜尋能力 |
| Retrieval filters 詞值、本次 filters | 僅影響查詢 |
| 顯示名稱 | 不更換穩定 collection |
| 未啟用／未引用服務的草稿 | 不改有效 Pipeline 或重建判定 |

「舊評估失效」是不能代表新版，不等於刪除歷史報告。Prototype 清除示意值的行為不應直接變成正式歷史資料刪除政策。

CSV 映射保存、Revision 計算、canonical JSON／Hash、部署綁定是否可重用資料版本需 Q-015 核定。邏輯 Config Hash 不混入部署 URL／認證／資料目標；部署綁定另記版本／識別以追蹤實際環境。不得記真實 Secret；有語意順序的陣列不可任意排序。

### 8.1 「重新 Ingestion／索引重建」的範圍

重建需說明受影響資料與需要重做的步驟，不一律代表清空整個資料庫。先前 Q-010／Q-015 的討論主要指有效 Ingestion 設定改變後，既有資料需要重新處理時的查詢可見性；以下區分不同情境：

| 情境 | 受影響範圍／需要的處理 |
|---|---|
| 新增來源文件 | 處理新增文件及其 Chunk／索引；不因新增就預設整批重建 |
| 更新單份文件內容 | 更新該文件產生的 Chunk／vectors／索引；舊片段替換與提交政策仍待 Q-008／Q-009 |
| 修改共用 Chunk Size／切分規則 | 重新處理採用該規則的既有文件，可能涵蓋此 System 全部文件；後續 Embedding／索引隨新的 Chunk 更新 |
| 更換 Embedding 語意 Profile | 針對受影響內容重算向量並建立相容的向量索引；是否可重用 Chunk 等中間產物待 Q-015 |
| 改 Indexing 欄位／Mapping | 重建或補建受影響索引能力；實際步驟由 ES／Local Adapter 及相容政策決定 |
| 只改 Query Transformation／Retrieval／Rerank／Generation | 不重做 Ingestion；重新測試／評估 |
| Local Memory 程序重啟 | 記憶體 Chunk／vectors／搜尋結構已遺失，需重新 Ingestion 才可 Query |
| Local MongoDB 程序重啟 | 以已保存 Chunk／vectors 恢復 FAISS／BM25／Chunk Store；相容時不需重新 Parsing／Embedding，屬索引恢復 |

是否阻擋 Query、允許舊版本持續服務，以及新增／單文件更新／整批重建是否採不同策略，仍待 Q-008～Q-010／Q-015；本節只是範圍釐清，不把所有情境定為相同鎖定或發布流程。

## 9. 待討論與決策

| ID | 本文件尚缺的決定 |
|---|---|
| [Q-002](08_implementation_plan.md#q-002) | 完整 Schema、Config 分支、型別／預設值／nullable、版本與 Prototype migration |
| [Q-003](08_implementation_plan.md#q-003) | 模型服務／Profile 的正式契約與多 Profile 範圍 |
| [Q-004](08_implementation_plan.md#q-004) | Tokenizer、溢位、長複製欄位 |
| [Q-006](08_implementation_plan.md#q-006) | 保留 metadata／ACL 名稱與可信來源 |
| [Q-007](08_implementation_plan.md#q-007) | ID／source_revision 演算法與檔案派生 |
| [Q-008](08_implementation_plan.md#q-008) | 同 ID／版本重送、更新及刪除 |
| [Q-013](08_implementation_plan.md#q-013) | 缺值、多值與 pre-filter 精確語意 |
| [Q-014](08_implementation_plan.md#q-014) | 已要求的融合策略／範圍／時點如何配置、路徑與預設 |
| [Q-015](08_implementation_plan.md#q-015) | Revision、Hash、Index 版本及映射變更 |

## 10. 交付與驗收要求

Q-002 核定後，開發階段需提供 Pydantic Models、可匯出的 JSON Schema、完整 Local／ES／MongoDB 範例與無效範例。相同資料在 UI／HTTP／直接 Engine 呼叫得到相容驗證結果；Unicode offset、向量維度及欄位路徑有獨立驗收資料。實作 Schema 是程式可驗證的產物，變更時同步更新本文與範例，不允許各層另創契約。
