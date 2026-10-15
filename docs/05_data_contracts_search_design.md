# RAG Builder — 共用資料模型與 Config 規格

> 文件集 v0.10 · 2026-10-15 · 開發規格草案
>
> 本文是資料形狀及設定規則的權威位置。已確認的語意保留；新增的程式型別、完整 Config 拼字與預設值為建議草案，待 Q-002 核定後才凍結。YAML 範例用於討論與驗收設計，目前沒有 Engine 可直接執行。

## 1. 範圍與讀法

- 模組如何執行見 [04](04_module_methods_io_contracts.md)，UI 見 [06](06_ui_development_spec.md)，HTTP 包裝／儲存見 [07](07_backend_runtime_integration.md)。
- 本文統一 ParsedDocument、Chunk、SearchHit、Config 及 ModuleResult，避免各模組重複定義。
- 物件形狀、Contract 版本與細節待 [Q-002](08_implementation_plan.md#q-002) 核定；已確認的五／六個頂層 key 不因此退回舊版。
- `?` 表示可省略，不自動表示可為 null；`JSON` 必須可序列化，數值不可為 NaN／Infinity。正式 required／nullable／additionalProperties 須由 Schema 定義。

## 2. 識別、版本與作用域

| 欄位／概念 | 語意 | 狀態 |
|---|---|---|
| system_id | 同一 RAG System 的穩定識別；租戶隔離仍由可信 Context 決定 | 已確認語意；格式待決 |
| document_id | 同一 System 中邏輯文件的穩定識別，不能用 Chunk ID 取代 | 已確認；產生演算法 Q-007 |
| source_revision | 文件內容版本，與 Config Revision 不同 | 已確認；省略時的生成／比較 Q-007 |
| chunk_id | 由文件、來源版本、切分有效設定與位置／序號產生 | 已確認方向；規範化／Hash Q-007 |
| config_revision | 平台保存的設定版本 | 已確認；草稿／生效語意 Q-015 |
| index_generation | 可追蹤的索引資料版本，不能把可變 alias 當 immutable snapshot | 已確認方向；切換 Q-010／Q-015 |
| contract_version | 資料／Config 契約版本 | 建議；遷移 Q-002 |
| run_id／request_id／trace_id | 批次工作、單次請求及追蹤識別 | 已確認方向；線上包裝 Q-019 |

CSV 每列是邏輯文件。跨批更新需映射穩定鍵；Prototype 的批次自動 ID 不能宣稱可跨次穩定。檔案拆為多份文件時保留來源資產關聯，不能讓所有列沿用同一 document_id。

### 2.1 collection 命名（已確認方向）

Builder 由 Workspace＋RAG System 名稱自動產生邏輯 collection，使用者不用手填。既有實作附穩定 System ID，避免同名及正規化碰撞；建立後改顯示名稱不更換實體名稱。UI 顯示唯讀，ES／Local／MongoDB 實體綁定由 Adapter 管理。正規化演算法、長度與匯入既有集合的權限規則仍屬 Q-007／Q-019，不重開「是否自動命名」的方向。直接 Engine 則使用 Config／可信 Binding 中明確的集合，不依賴 Builder 才可運作。

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

## 5. 共用執行與錯誤物件

下列延續舊 04 的設計方向，正式欄位必填與狀態仍由 Q-002／Q-017 核定：

| 物件 | 建議欄位 |
|---|---|
| ModuleConfig | module_id、implementation_version、contract_version、method、parameters、服務引用 |
| RunContext | system_id、config_revision、run_id／request_id、trace_id、deadline、attempt、可信 auth_scope |
| ModuleResult[T] | status: succeeded／partial／failed，data、errors、warnings、metrics |
| ModuleError | code、module、message、retryable、item_id?、details? |
| ExecutionMetrics | duration_ms、input_count、output_count、token_usage?、provider_request_id? |

failed 時 data 為 null；partial 必須能對應成功／失敗／skipped 項目，不能默默少資料。哪些模組允許 partial 及如何提交資料仍受 Q-009 限制。HTTP 任務狀態不是 ModuleResult.status，見 07。

未知 Token Usage 為 null／省略，不填 0。Secret 與敏感原文不進錯誤／追蹤。使用者無權設定可信租戶／ACL Context。

## 6. Config 結構與有效設定

### 6.1 草稿、有效 Config 與部署覆寫

- UI Draft 保存基本／進階欄位及未啟用方法的草稿；不是所有欄位都參與執行。
- Effective Config 僅包含使用中的方法、參數、服務及欄位；AI 與手動入口共用編譯／驗證。
- Deployment Override 只替換目標環境連線／Secret 等允許項，不修改平台測試 Config。
- 更換 Embedding 語意 Profile 不能當作純環境覆寫，必須重新 Embedding／Indexing。
- 使用相同服務的兩個模組引用同一 llm_ref；匯出只包含實際引用的服務。

以下根結構為**建議**：contract_version、document_schema、llms、pipelines.ingestion、pipelines.inference、execution。System／Revision／IndexBinding 為管理與執行綁定，Engine 由參數／Context 取得；HTTP／Blueprint 包裝見 07。

### 6.2 模組設定詞彙

| 模組 | 已確認語意 | 本版建議 Config 欄位 |
|---|---|---|
| Import | files／records；CSV 先映射到 records | accepted_inputs、csv_mapping |
| Parsing | 格式路由、結構化 records 驗證 | routes |
| Chunking | Recursive／Header-aware；Token 計量 | method、split_field、copy_fields、metadata_fields、size、overlap、tokenizer、separators、keep_separator、header_levels |
| Embedding | fields → 命名 vectors | profile、mappings（source_field、output_name） |
| Indexing | 儲存、全文、向量、過濾分開 | backend、collection、stored_fields、fulltext_fields、vector_fields、filter_fields、persistence、metric |
| Query Transformation | None／Rewrite／Multi-query | method、llm_ref、prompt、count、include_original |
| Retrieval／Fusion Plan | 選已索引欄位、推導模式；可配置策略及合併時點 | fulltext_fields、vector_fields、per_route_k、top_k、filters、fusion；stages／scope／placement 具體 Schema 待 Q-014 |
| Rerank | None／DEV／Rerank API | method、service、content_fields、top_n |
| Generation | 兩層模板、共用 LLM | llm_ref、chunk_template、prompt、temperature、max_output_tokens、context_budget |

正式枚舉建議用 snake_case，UI 可顯示自然語言。Prototype 的 chunking.split、embedding.mappings[].source、indexing.filters、transform 等短名稱不自動視為正式 Schema；需明確 migration。統一使用完整路徑 fields.text／vectors.text_vector／metadata.department。上述拼字及預設值需 Q-002 核定，禁止同時接受未宣告別名而掩蓋錯誤。

### 6.3 參數與相依規則

| 條件 | 驗證 |
|---|---|
| Token Chunking | size 為正整數；0 ≤ overlap < size；Tokenizer 可取得；Header-aware 需 headings 能力 |
| Embedding mappings | 來源為有效文字欄位；output_name 唯一；有限值、維度與 Profile 相容 |
| Indexing | 搜尋欄位與上游一致；必要識別／來源／ACL 強制保留；下游使用欄位已保存 |
| Retrieval | 至少一路；每路及最終 K 為正整數；僅選已建立索引；Query Profile 由向量欄位繼承 |
| Fusion | 多 Query／多欄位需有明確計畫；基線為單層 Rerank 前，目標支援時點選擇；只使用已選策略有效參數 |
| Sum Score | 現有單層基線的預設；全文／向量權重預設各 1，有限非負，使用中至少一個大於 0；不自動正規化 |
| RRF | rank 從 1；k 預設 60 且為正整數；k 與 Top-K 不同 |
| Rerank | None 不執行且不使用 top_n；啟用時 0 < top_n ≤ Retrieval top_k |
| Templates | 只允許宣告變數；單次替換；未知／必要變數缺少阻止保存 |
| LLM | 引用有效；刪除使用中的服務不得默默換另一個 |

純 BM25 可跳過 Embedding，但 Chunking 仍需 Tokenizer。複製欄位長度可能大於 Chunk Size，Embedding 必須逐項檢查實際輸入。Tokenizer、模型極限及溢位政策見 Q-004。

**融合配置的目標要求已存在，細節尚待 Q-014**：必須能區分演算法、融合範圍（同 Query／跨 Query）與執行時點（Rerank 前／後）。可選兩層及預設計畫的精確支援範圍、route 型別、Top-K／Top-N 與分數語意需再核定；不能把全部合併為一個 fusion.method 後宣稱符合需求。`fusion.stages[]` 是先前助理提出的 Schema 候選，尚非已定欄位。

### 6.4 過濾條件

```json
[{"field":"metadata.department","operator":"eq","value":"manufacturing"}]
```

Indexing 宣告可過濾欄位；Retrieval 保存預設條件；Query API 可加本次條件。全部與後端強制授權 AND；in 清單內為任一值符合。第一版 eq 為非空字串，in 為非空、不重複字串清單。空條件清單不增加業務限制，不能取消 ACL。

所有 Query × 欄位路徑須在取 Top-K 前套用相同限制。缺值／null／多值精確語意與 Adapter 可用能力見 Q-013；不支援就拒絕配置。數值／日期／OR 群組列為後續。

## 7. 完整 Config 範例（建議草案）

以下是 **既有單層融合基線的完整 Local Search／Memory 配置草案**，不是完整實現合併時點需求的最終配置。服務 URL 為不可運作的 `.invalid` 網域，Secret 只示意引用；可作 Schema 設計與測試材料，現在沒有 Engine 可執行。Q-002／Q-014 核定後應另提供 Fusion Plan 範例、migration 與 Schema 驗證。

```yaml
contract_version: "0.1-draft"
document_schema:
  fields:
    - {name: text, type: string, required: true, source: input}
    - {name: title, type: string, required: false, source: input, default: ""}
  metadata:
    - {name: department, type: string, required: true, source: input}
  unknown_fields: reject
llms:
  - id: llm-default
    name: Default LLM
    service:
      provider: openai_chat
      base_url: https://llm.example.invalid/v1
      model_id: chat-model
      auth: {type: bearer, secret_ref: llm-token/key}
      timeout_seconds: 30
pipelines:
  ingestion:
    import:
      accepted_inputs: [records]
      csv_mapping:
        id: document_id
        content: fields.text
        title: fields.title
        department: metadata.department
    parsing:
      routes: {records: structured_records}
    chunking:
      method: recursive
      split_field: fields.text
      copy_fields: [fields.title]
      metadata_fields: [metadata.department]
      size: 512
      overlap: 64
      tokenizer: {id: tokenizer-example, revision: pinned-example}
      separators: ["\n\n", "\n", "。", " ", ""]
      keep_separator: true
    embedding:
      profile:
        profile_id: embedding-default
        service:
          provider: openai_embeddings
          base_url: https://embedding.example.invalid/v1
          model_id: embedding-model
          auth: {type: bearer, secret_ref: embedding-token/key}
          timeout_seconds: 30
        model_version: pinned-example
        dimension: 768
        vector_kind: dense
        document_encoding: {prefix: ""}
        query_encoding: {prefix: ""}
        normalization: l2
        tokenizer: {id: tokenizer-example, revision: pinned-example}
        max_input_tokens: 8192
      batch_size: 16
      mappings:
        - {source_field: fields.text, output_name: text_vector}
    indexing:
      backend: local_search
      collection: workspace-manual-system-example
      persistence: {mode: memory}
      metric: cosine
      stored_fields: [fields.text, fields.title]
      fulltext_fields: [fields.text]
      vector_fields: [vectors.text_vector]
      filter_fields: [metadata.department]
  inference:
    query_transformation: {method: none}
    retrieval:
      fulltext_fields: [fields.text]
      vector_fields: [vectors.text_vector]
      per_route_k: 10
      top_k: 5
      filters: []
      fusion:
        method: sum_score
        score_weights: {fulltext: 1, vector: 1}
    rerank: {method: none}
    generation:
      llm_ref: llm-default
      temperature: 0.2
      max_output_tokens: 1024
      context_budget: 4000
      chunk_template: "[{{citation_id}}] {{fields.title}}\n{{fields.text}}"
      prompt: "請根據參考資料回答並標示引用。資料不足時請明確說明。\n參考資料：\n{{context}}\n問題：{{query}}"
execution:
  request_timeout_seconds: 120
  max_attempts: 1
```

本例的模型維度、Token 上限、Timeout 與名稱均為示例；不能把示例 Profile 套到任意實際模型。max_attempts=1 表示尚未啟用自動重試，不宣稱重試政策已定案。

ES 變體需使用自己的連線／Secret、Mapping 與能力驗證；MongoDB 變體需提供 DB／Collection、Profile Manifest 與重建政策。這些正式配置分支及 DEV service_ref 的 Schema 由 Q-002／Q-012／Q-021 核定，不能僅把 backend 字串換掉就視為完整。

## 8. Config 變更影響矩陣

| 有效變更 | 影響 |
|---|---|
| Document Schema、Import／Parsing／Chunking／Embedding／Indexing、資料目標 | 標記需重新 Ingestion；重建流程是否可重用中間產物另決 |
| Query Transformation、Retrieval、Rerank、Generation、被引用的 LLM | 不需重建；需重新測試／評估 |
| Indexing filter_fields | 需重建搜尋能力 |
| Retrieval filters 詞值、本次 filters | 僅影響查詢 |
| 顯示名稱 | 不更換穩定 collection |
| 未啟用／未引用服務的草稿 | 不改有效 Pipeline 或重建判定 |

「舊評估失效」是不能代表新版，不等於刪除歷史報告。Prototype 清除示意值的行為不應直接變成正式歷史資料刪除政策。

CSV 映射保存、Revision 計算、canonical JSON／Hash 演算法、部署覆寫是否重用已驗證資料版本需 Q-015 核定。Hash 不能包含未解析 Secret 或時間戳而失去可重現性；有語意順序的陣列不可任意排序。

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
