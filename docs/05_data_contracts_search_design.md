# RAG Builder — 資料契約與索引設計討論結論

> 2026-10-14 · 設計草案 v0.5
>
> 整理本輪 Import／Parsing／Chunking／Embedding／Indexing／Retrieval 討論。這是設計規格；UI Prototype 已加入互動示意，Engine／API／DB 尚未實作。
> 本文取代《04_module_methods_io_contracts.md》v0.2 中關於 ParsedDocument、Chunk、獨立 VectorSet、多欄位與搜尋後端的舊提案；其他模組的執行、錯誤與評估契約仍沿用原文件。

## 1. 決策狀態

| 項目 | 結論／狀態 |
|---|---|
| 統一資料物件 | ParsedDocument 五個頂層 key；Chunk 六個頂層 key，新增 vectors |
| 模組分工 | Parsing 擷取及映射；Chunking 切分及繼承；Embedding 產生向量；Indexing 儲存及建索引 |
| 多欄位 | 可分別選擇 Embedding、Indexing、Retrieval、Rerank、Generation 使用的欄位 |
| 搜尋後端 | 已確認 ES／Local Search（FAISS＋BM25）；後端待實作驗證 |
| 持久化 | Local Search 支援 Memory／MongoDB 的設計方向；MongoDB 不執行該模式的向量搜尋 |
| 使用介面 | 後端共用設定流程，能力差異以顯示但停用及原因說明處理 |
| Hybrid | 第一版使用 RRF；正規化後加權分數融合為後續選項 |
| 第一版切分 | 一個主要切分欄位＋多個複製欄位；Recursive／Header-aware，使用 Token 計量 |
| 多模態 | 第一版建議文字 RAG；OCR 首批格式及實作待定，視覺描述／圖片 Embedding 暫列後續 |
| 摘要 | 先使用輸入已有摘要；自動摘要 Enrichment 為後續能力 |
| 客製化 | 優先考慮 Chunking、Query Transformation、Rerank、Evaluation；不代表已實作 |

## 2. 模組責任與資料流

| 模組 | 目的 | 主要輸入 | 主要輸出 | 不屬於本模組的責任 |
|---|---|---|---|---|
| Import | 接收資料、驗證與保存原始輸入及來源資訊 | 檔案上傳／API 請求 | SourceAsset 清單 | OCR、內容解析、Embedding |
| Parsing | 依格式擷取內容、欄位映射與結構資訊 | SourceAsset 清單 | ParsedDocument 清單 | 自動產生搜尋向量 |
| Chunking | 切分主要內容，複製指定內容與 metadata，產生位置 | ParsedDocument 清單 | Chunk 清單，vectors={} | 預設回查父文件、自動產生摘要 |
| Embedding | 讀取指定 fields，將向量寫入 vectors | Chunk 清單 | 帶 vectors 的 Chunk 清單 | 建立搜尋索引 |
| Indexing | 儲存 Chunk，依欄位用途建索引 | 帶向量或純文字的 Chunk 清單 | IndexBinding、寫入及可搜尋狀態 | 重新執行內容 Embedding |
| Retrieval | 查詢已建立索引，融合候選並取回完整 Chunk | Query、IndexBinding、filter | SearchHit 清單 |
| Rerank | 依問題與選定內容欄位重排 | SearchHit 清單 | 重排後的 SearchHit 清單 |
| Generation | 依指定內容欄位組 Context 並回答 | 問題、歷史、SearchHit 清單 | 回答、引用、使用量與追蹤資訊 |

Indexing 與 Inference 以持久化或記憶體中的索引銜接，不是同一次串行函式呼叫。Config、RunContext、Embedding Profile 與 IndexBinding 是控制資訊，平台另外提供；不需塞進每個 Chunk。

Import 預設可同時提供上傳與 API 入口，不要求使用者二選一。外部呼叫 Ingestion API 與平台主動拉取外部 API 是不同能力。CSV／Excel 通常以「每列」成為一份邏輯文件，欄位轉成 JSON 欄位；不是每一個 column 都是一份文件。檔案解析與列到文件的映射規則由 Parsing 負責。

## 3. ParsedDocument：五個固定頂層 key

| Key | 型別 | 語意 |
|---|---|---|
| document_id | string | 同一邏輯文件的穩定識別 |
| source_revision | string | 來源內容版本 |
| fields | object | 原文、標題、摘要等後續模組需要的內容 |
| metadata | object | 來源、分類、權限及處理資訊 |
| structure | object | 依 fields 欄位對應的區塊、頁碼、段落位置；可為 {} |

範例（位置範圍與文字長度一致）：

```json
{
  "document_id": "doc-001",
  "source_revision": "v1",
  "fields": {
    "text": "第一段。第二段。",
    "summary": "文件摘要",
    "title": "設備維修手冊"
  },
  "metadata": {
    "source_uri": "manual.pdf",
    "department": "manufacturing"
  },
  "structure": {
    "text": {
      "blocks": [
        {"block_id": "b1", "kind": "text", "start": 0, "end": 4, "page_number": 1},
        {"block_id": "b2", "kind": "text", "start": 4, "end": 8, "page_number": 2}
      ]
    }
  }
}
```

位置規約：start／end 為對應 fields 欄位完整字串的 Unicode code point offset，0-based、半開區間；page_number 從 1 起。此規約取代舊版 block 內 offset 的提案。標題結構、表格等可擴充 structure，但需有型別定義。

Import 可先給來源資產 ID。若一個 Excel／JSON 批次解析成多份文件，Parsing 應根據穩定列主鍵等規則派生不同 document_id，保留來源資產關聯；不能讓所有列沿用同一文件 ID。沒有穩定列鍵時，需明確定義更新與重新匯入規則。

## 4. Chunk：六個固定頂層 key

| Key | 來源／責任 |
|---|---|
| chunk_id | Chunking 依文件、版本、切分設定與位置確定性產生 |
| document_id | 繼承 ParsedDocument |
| source_revision | 繼承 ParsedDocument |
| fields | 切分後的內容＋設定要複製的內容 |
| vectors | Chunking 初始化為 {}；Embedding 寫入具名稱的向量 |
| metadata | 繼承指定資訊＋衍生的片段位置與處理資訊 |

```json
{
  "chunk_id": "doc-001:v1:c1",
  "document_id": "doc-001",
  "source_revision": "v1",
  "fields": {
    "text": "第一段。",
    "summary": "文件摘要",
    "title": "設備維修手冊"
  },
  "vectors": {},
  "metadata": {
    "source_uri": "manual.pdf",
    "department": "manufacturing",
    "locations": [
      {"field": "text", "start": 0, "end": 4, "page_number": 1, "block_id": "b1"}
    ]
  }
}
```

Chunk 應自帶 Rerank／Generation 需要的內容，不強制回查 ParsedDocument。ParsedDocument 可選擇保存，供除錯與重新切分；Parent–Child Retrieval 不列入此基本流程。

fields／metadata 可擴充，但每個 RAG System 要宣告 Content Schema，包含欄位名稱、型別、是否必填及缺值政策。權限、來源、系統識別及 locations 等保留欄位由平台管理，不允許使用者覆寫。舊版頂層 access_policy_ref、parser_version、chunking_signature 等資訊應移入明確宣告的 metadata 保留區或平台執行紀錄。

搜尋分數、rank、matched query 與 rerank score 屬 SearchHit／Trace，不是 Chunk 內容。後續檢索回傳可將 vectors 設為 {}，避免將大向量傳入 Rerank／Generation；持久化副本仍保留完整向量。

## 5. Parsing 與 Chunking 設定

### 5.1 多個 Parser 共存

不同格式透過 routing 選用不同 Parser；同一格式可選一種解析策略。格式路由與執行時平行處理是不同設定，不應混為同一概念。

| 輸入 | Parsing 處理 | 統一輸出 |
|---|---|---|
| PDF 文字層 | 文字、頁碼、區塊擷取 | fields＋structure |
| 掃描 PDF／圖片 | OCR | 文字＋可用的位置資訊 |
| PPTX | 文字、投影片頁次、區塊擷取 | fields＋structure |
| TXT／Markdown | 文字與可用章節結構 | fields＋structure |
| CSV／Excel | 列到文件、column 到欄位映射 | 一份或多份 ParsedDocument |
| API JSON | 驗證與欄位映射 | ParsedDocument 清單 |

統一結構不代表所有來源都有頁碼或章節。未啟用 OCR 的掃描文件，不應以空文字成功進入索引。

Parsing 不產生向量。OCR 讀取文字，不保證理解流程箭頭、圖表或照片；視覺模型產生描述及多模態 Embedding 為後續功能。未來圖片以資產引用進入 fields，Embedding 讀取實際圖片內容，不能把 URI 字串當作圖片 embedding。

### 5.2 Chunking 欄位策略

第一版建議：
- split_field：一個主要文字欄位，例如 fields.text。
- copy_fields：例如 fields.title、fields.summary，複製到每個 Chunk。
- metadata_fields：選擇繼承的來源／分類資訊；必要權限強制保留。
- locations：根據切分範圍與 structure 計算，可能跨多頁或多區塊。
- size／overlap：統一以 Token 計量；Tokenizer 預設沿用 Embedding，也可自行指定。Recursive／Header-aware 的邊界設定見第 13 節。

複製的文件摘要仍是文件層級摘要，不會自動變成 Chunk 摘要。若摘要重複出現在同文件的所有 Chunk，摘要向量搜尋可能回傳多個同文件片段；後續需依需求進行文件分組或片段 Rerank。

## 6. Embedding：fields → vectors

```yaml
embedding:
  mappings:
    - source_field: fields.text
      output_name: text_vector
      profile_ref: embedding-a
    - source_field: fields.summary
      output_name: summary_vector
      profile_ref: embedding-a
```

Embedding 後，Chunk 的 vectors 例如：

```json
{
  "text_vector": [0.12, 0.34, 0.56],
  "summary_vector": [0.23, 0.45, 0.67]
}
```

三維數值僅為示例。每個 output_name 綁定 Profile：來源欄位、模型／版本、維度、document/query encoding、normalization。設定由平台保存，不在每筆 Chunk 重複。向量名稱為邏輯名稱，後端實體欄位由 Adapter 映射。

驗證：來源欄位型別與缺值政策、輸出名稱唯一、向量值有限、維度與 Profile 相容。第一版優先 Dense；Sparse 的值型別需另定，不能把 Dense 陣列與 Sparse 權重混用。多個具名稱向量不等於 late-interaction 的每欄位多向量模型。

本版 Embedding 業務 I/O 為 chunks → chunks（填入 vectors）；不再以獨立 vector_sets 作為主要傳遞方式。純 BM25 可略過 Embedding。

## 7. Indexing：儲存與索引分開設定

| 設定用途 | 來源 | ES 對應示例 |
|---|---|---|
| 全文搜尋 | fields 的文字欄位 | text |
| 向量搜尋 | vectors 的命名向量 | dense_vector；Sparse 為後續 |
| 精確過濾／分組 | fields、metadata 或固定 ID | keyword |
| 數值／日期範圍 | fields／metadata 的型別欄位 | integer、float、date 等 |
| 僅保存內容 | 後續 Rerank／Generation 所需欄位 | 保存內容而不提供對應搜尋能力 |

儲存欄位不等於建立搜尋索引。平台的「保存」也不等同 ES 的 store:true 設定；實體 Mapping 由 Adapter 負責。完整文件 ID、版本、權限等必要資訊固定保留。

ES 一個邏輯 index 可容納多種欄位 Mapping；其底層仍有不同欄位的搜尋結構。Hybrid 是 Retrieval 的查詢與融合策略，不是第三種欄位型別。

```yaml
indexing:
  backend: local_search
  persistence: memory
  stored_fields: [fields.text, fields.summary, fields.title]
  vector_fields: [vectors.text_vector, vectors.summary_vector]
  fulltext_fields: [fields.text]
  filter_fields: [metadata.department]
  group_fields: [document_id]
```

以上為平台設定示例，不是任何資料庫的原生 API。

## 8. 後端選型與持久化

### 8.1 角色區分

- Elasticsearch：整合文件儲存、全文與向量搜尋；本輪已選為其中一個後端。
- FAISS：向量索引與搜尋函式庫，不提供完整文件資料庫或原生 BM25。
- Local Search：平台組裝的 FAISS＋BM25＋候選融合＋Chunk Store；不是 FAISS 產品自帶功能。
- MongoDB：Local Search 模式的選配長期儲存，保存 Chunk（含 vectors）及相關設定，不執行該模式的向量搜尋。
- LanceDB、Qdrant、MongoDB Search／Vector Search 曾作為替代方案討論，未列入本版兩個後端的實作範圍。

### 8.2 建議運作模式

| 項目 | ES | Local Search／Memory | Local Search／MongoDB |
|---|---|---|---|
| 完整 Chunk | ES | 記憶體 | MongoDB，可載入記憶體快取 |
| 向量搜尋 | ES | FAISS | FAISS |
| 全文搜尋 | ES | 平台 BM25 實作 | 平台 BM25 實作 |
| 程序重啟 | 使用既有索引 | 資料遺失，重新 Ingestion | 讀取 Chunk／vectors 重建 FAISS 與 BM25 |
| 重新 Embedding | 依內容／設定變更需要 | 重新 Ingestion 時需要 | 模型設定未變且向量完整時不需要 |
| 定位 | 完整搜尋服務 | 小型試用／Prototype | 需要保存資料的小型服務 |

網路暫時斷線不等於記憶體消失；程序結束／Pod 被替換才會遺失。FAISS 可存檔；Memory 模式不保存是第一版選擇，並非工具限制。

第一版 Local Search 建議單一服務程序承接 Ingestion／Inference。多 worker／多 Pod 不會自動共享記憶體索引；MongoDB 持久化也不會自動同步各 Pod 的 FAISS，後續需額外的版本通知與索引載入設計。沒有 MongoDB 時，不應將 Ingestion 獨立成執行完即退出且不交付索引的 Job。

### 8.3 多欄位的內部實作

每個命名向量欄位建議各自一個 FAISS index，兩者的向量 ID 都映射至 chunk_id；完整 Chunk 只保存一份。BM25 使用另外的文字索引。原文與摘要即使維度相同，也不預設混在同一索引。

以上屬後端細節。UI 一律選後端、來源欄位與用途，不要求使用者管理 FAISS index 數量。

## 9. Retrieval、融合與文件分組

Retrieval 只能選擇已建索引的欄位。向量查詢的模型、維度、encoding 由對應 Profile 繼承，不讓使用者任意選另一模型。Rerank／Generation 則選可取得的內容欄位，不必要求該欄位本身可搜尋。

Hybrid 可採：
- RRF：sum(1 / (k + rank))；未出現在某一路候選則該路貢獻為 0。k 是平滑常數，不是 Top-K。可擴充權重。
- 加權分數融合：sum(weight × normalized_score)。需先統一方向與尺度；BM25、cosine 與距離不可直接假設可比較。

第一版使用 RRF，逐路 Top-K 與融合後候選 Top-K 分開定義。ES 需配置查詢及融合；不是建好索引就自動 Hybrid。Local Search 由平台負責 BM25、FAISS 結果融合。

| 操作 | 識別依據 | 責任 |
|---|---|---|
| 多路命中合併 | 相同 chunk_id | Retrieval 融合階段，不依賴 Rerank |
| 同文件片段限制 | 相同 document_id、不同 chunk_id | 文件分組／max_chunks_per_document 策略 |
| 語意重排 | 問題＋指定內容欄位 | Rerank |

文件分組不是刪除重複 chunk_id。可在 Retrieval 限制文件占比，或 Rerank 後選每文件最佳片段；先做可能失去有用片段，因此不預設每文件只能一個 Chunk。ES 可用 document_id collapse／inner_hits 達成部分需求，但與特定向量、RRF 查詢的組合須依目標版本驗證，不能宣告所有組合可用。

Local Search 的 filter 必須有明確語意。尤其系統隔離及 ACL 不能只靠全域 Top-K 後刪除不合法結果；實作需採隔離索引、授權候選集合搜尋等可靠方式，未支援時應停用相關配置。

## 10. UI 相依卡控

| 上游條件 | 下游行為 |
|---|---|
| Parsing 輸出 Schema | Chunking 可選欄位及方法據此產生 |
| Chunking 輸出 fields | Embedding 僅選有效且型別相容欄位 |
| Embedding mappings | Indexing 僅選已宣告 vectors；維度唯讀繼承 |
| Indexing 欄位／能力 | Retrieval 僅選已建立的搜尋路徑 |
| 只有向量或只有全文 | Hybrid 顯示但停用 |
| 未提供可用全文 Adapter | BM25／Hybrid 顯示但停用，即使 UI 後端叫 Local Search |
| Rerank／Generation 選用欄位 | 必須保證已儲存並可取得 |
| Rerank=None | Top-N 保留顯示但停用，不進有效 Config |
| Top-N 大於候選 Top-K | 阻止儲存有效設定並顯示原因 |

上游修改使既有選項失效時，保留選擇並標記，不默默替換。前端卡控與後端 Validator 共用能力宣告。不同後端共用操作方式，但不能假裝能力完全一致。

## 11. 客製化與後續待確認

Custom Python 保持固定 I/O、Config Schema 與語意驗證。優先開放 Chunking、Query Transformation、Rerank、Evaluation；Import／Parsing／Embedding／Indexing／Retrieval 優先以註冊 Adapter 擴充。Generation 先提供 Prompt、內容欄位與輸出格式設定。

尚待確認：
1. 首批 Parser、OCR 與格式範圍。
2. FAISS＋BM25 的具體套件、中文斷詞與索引規格。
3. Local Search 的 Hybrid／過濾效能與可支援資料量實測。
4. metadata 的保留欄位、ACL 與 filter 實作。
5. 缺欄位處理、文件／Chunk ID 規則與來源更新策略。
6. 文件分組的預設位置、每文件片段數與評估方式。
7. MongoDB 的索引版本、恢復流程及更新／刪除一致性。
8. 是否保留原始檔及 ParsedDocument，供重新 Ingestion 使用。

本次同步修改 UI Prototype，尚未實作 Engine。實作時須同步更新舊 Contract 與 Registry，避免仍使用 Chunk.text、獨立 VectorSet 或單一向量 Profile 假設。

## 12. 官方參考

以下供實作驗證能力使用；本文的資料物件與配置是平台自訂設計。

- Elasticsearch 欄位型別：https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/field-data-types
- Elasticsearch Dense vector：https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector
- Elasticsearch RRF Retriever：https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rrf-retriever
- Elasticsearch Collapse：https://www.elastic.co/docs/reference/elasticsearch/rest-apis/collapse-search-results
- FAISS 索引讀寫：https://github.com/facebookresearch/faiss/wiki/Index-IO%2C-cloning-and-hyper-parameter-tuning
- LangChain FAISS 整合：https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/vectorstores/faiss.py


## 13. 2026-10-14 已確認：設定介面與服務來源

本節整合本輪決策；UI Prototype 已提供互動示意，Engine／API／資料庫尚未實作。先前 v0.3 的候選設計若有衝突，以本節及更新後的決策表為準。

### 13.1 Chunking：兩種方法，統一 Token 計量

- Recursive：依分隔符優先順序切分過長內容。
- Header-aware：先依標題層級切分，超長章節再使用 Recursive。
- Sentence-aware 暫不納入；切分方法下方不再提供字元長度模式。
- 參數：Chunk Size、Overlap（皆為 Tokens）、Tokenizer ID／revision、分隔符清單及順序、keep_separator。Header-aware 另有標題層級。
- 預設沿用 Embedding 對應 Tokenizer，也允許自行指定；純 BM25 不需要 Embedding 呼叫，但切分仍需要 Tokenizer。
- Size 是上限，不是每塊必須等長；保留自然邊界時，Overlap 是目標值。
- 更換 Tokenizer 或切分參數需要重新切分。只有 Embedding 模型改變而 Tokenizer 相同時，理論上可重用 Chunk，但仍需重新 Embedding；prototype 統一標示需重新 Ingestion。
- 輸入上限還要包含特殊 Token、前綴及組合內容。複製到 Chunk 的文件摘要未經主要欄位切分，Embedding 執行時要逐筆檢查，不能只檢查 Chunk Size。
- Parser 未提供可靠標題結構，Header-aware 不能執行。Prototype 的「保留標題結構」是能力配置示意，並未驗證真實文件。

### 13.2 共通服務來源：DEV test use／自行提供

| 模組／條件 | 選項 | 自行提供時的設定 |
|---|---|---|
| Embedding | DEV test use／Embedding API | Base URL、Model ID、認證、Secret 引用、Timeout、維度、Tokenizer／revision、Token 上限、Batch Size |
| Indexing = ES | DEV test use／Elasticsearch | URL、認證、Secret 引用、Timeout |
| Local Search = Memory | 不需要 DB | 程序重啟需重新 Ingestion |
| Local Search = MongoDB | DEV test use／MongoDB | 不含帳密的 URI、Database、Secret 引用、Timeout |
| LLM 共用服務設定 | DEV test use／OpenAI-compatible API | 服務名稱、Base URL、Model ID、認證、Secret 引用、Timeout |
| Query Rewrite／Multi-query | 下拉選擇共用 LLM | 各方法的 Prompt、Query 數及原始問題選項 |
| Rerank | None／DEV test use／Rerank API | Base URL、Model ID、認證、Secret 引用、Timeout |
| Generation | 下拉選擇共用 LLM | 兩層模板與生成參數；連線設定由共用 LLM 繼承 |

DEV 使用平台預先設定的資源，UI 顯示模型資訊而不暴露憑證。Prototype 不提供真實 DEV 服務：模型名稱及 Tokenizer 是示例；Check Settings 僅驗證格式，不會測試連線。正式 Engine 再實作實際測試 API／模型維度與連線的能力。

Embedding API 第一版約定 OpenAI-compatible embeddings 介面（Base URL 下的 /embeddings），Generation／Query Transformation 約定 Chat Completions（/chat/completions）。API URL 不能取代 Request／Response 契約；其他格式需 Adapter。Authentication 與必要參數由具體 Adapter 實作。

Prototype 僅填寫 secret-name/key 引用，不輸入或匯出真實憑證。DEV 下停用的 URL／認證草稿不進有效配置。部署環境需自行建立相關 Secret。

### 13.3 Index collection 自動產生

- 由 Workspace＋RAG System 顯示名稱正規化，再附穩定 System ID，以免同名或中文名稱正規化後碰撞。
- 例如 customer-support-product-faq-a1b2c3。
- UI 顯示唯讀名稱；ES index／Local Search 邏輯集合及 MongoDB Collection 由 Adapter 綁定。
- 修改系統顯示名稱不改既有實體 collection；建立後保留穩定名稱。

### 13.4 多 Query 與 Retrieval

Query Transformation 提供 None／Rewrite／Multi-query。Rewrite 產生一個衍生問題，Multi-query 產生多個表述，另有「將原始問題也加入搜尋」選項。count 表示產生的 Query 數量，不含原始問題。原始問題永遠保留給 Rerank／Generation。

各 Query × 各搜尋欄位建立搜尋路徑，各路取候選後，在 Retrieval 以 chunk_id 融合成一份清單，再進入 Rerank。Rerank 關閉也不影響融合。

Retrieval 不再選 Implementation 或 Dense／BM25／Hybrid。直接選已建立索引的全文／向量欄位，平台顯示推導模式；後端從 Indexing 繼承。設定每路候選 Top-K、最終候選 Top-K；多路時提供 RRF 與平滑常數。多個向量欄位或多 Query 同樣需要融合，不以 Hybrid 作唯一啟用條件。

### 13.5 Rerank 平台契約

以下是平台選定的第一版格式，不宣稱是所有模型服務的共通標準。POST {Base URL}/rerank：

```json
{
  "model": "reranker-a",
  "query": "原始問題",
  "documents": ["候選內容 A", "候選內容 B"],
  "top_n": 2
}
```

```json
{
  "results": [
    {"index": 1, "score": 0.92},
    {"index": 0, "score": 0.61}
  ]
}
```

documents 每個字串由一筆 Chunk 的選取欄位依序組合。index 是輸入候選的 0-based 序號；score 越大越相關。Adapter 驗證序號唯一、範圍合法及分數有限，對回 chunk_id。Rerank 輸出不能新增候選，Top-N 不超過 Retrieval Top-K；None 時不匯出 Top-N／模型連線設定。

### 13.6 Generation：兩層模板

「參考資料格式」逐筆套用：

```text
[{{citation_id}}] {{fields.title}}
{{fields.text}}
```

多筆套用後組合為 context；回答 Prompt 使用：

```text
請根據以下參考資料回答問題，並標示來源編號。
若資料不足，請明確說明。

參考資料：
{{context}}

問題：{{query}}
```

- citation_id 由平台產生並對應 chunk_id；query 是原始問題。
- 參考資料格式只可引用已儲存 fields；回答 Prompt 支援 context／query，聊天歷史另由 messages 傳入。
- 可插入變數、檢查未知變數與空模板，並預覽替換後的示例。
- 替換一次，不遞迴解析文件文字內的 {{...}}；不執行程式或任意模板邏輯。
- Generation 的「模板說明與範例」按鈕展示兩筆 Chunk → 逐筆模板 → context → 完整 Prompt，並提供套用範例。
- 具備 Temperature、輸出 Token 上限與 Context Budget。Runtime 需以生成模型的 Tokenizer 計算整體預算；prototype 預覽不執行 Tokenizer 或截斷。

### 13.7 AI 設定助手與 Edit Config

AI 設定助手：描述需求／提供樣本 → 產生建議 → 顯示差異 → Validator → 使用者套用到草稿 → Create／Save 才生效。助手只能使用平台支援的欄位與方法，不能猜測憑證或自動啟動 Ingestion。

Prototype 使用明示的本機規則模擬，並非 LLM：可讀 ≤1 MB JSON／CSV／TXT／MD 的樣本欄位，支援 content／abstract／title 等映射；可示範改用 Local Search／MongoDB／Memory、原文切分且摘要複製、只搜尋原文及 Multi-query。未知需求會說明未支援；不假裝解析 PDF／PPTX／Excel。手動改動草稿後，舊建議不能覆蓋，需重新產生。

已建立的系統提供 Edit Config，重用 Create 介面。編輯使用獨立草稿，取消不影響現有配置。儲存前列出變更模組及影響：

| 變更 | 行為 |
|---|---|
| Parsing／Chunking／Embedding／Indexing 的有效配置 | 標記需重新 Ingestion，完成前阻止新版 Inference／Evaluation |
| Query Transformation／Retrieval／Rerank／Generation | 不需重新 Ingestion，清除舊示意回答／評估結果並建議重測 |
| 顯示名稱 | 更新名稱，collection 保持不變 |
| 未啟用的服務草稿欄位 | 不納入有效配置比較，不因而標記重建 |

ES／DB 連線更換也歸為需重新 Ingestion；不能假設目標環境已有相同資料。Prototype 不實作新舊索引雙版本切換；正式 Runtime 需定義其一致性策略。

### 13.8 匯出與實作界線

Export 對使用中的外部依賴逐項檢查。可下載含 DEV 標記的「待設定草稿」，或填寫自己的 URL／認證引用後下載「已填妥設定」；後者只是格式驗證通過，不代表服務可連線或可直接部署。

部署覆寫不改平台內測試配置。若改 Embedding Model，先回 Edit Config 調整完整 Profile 並重新 Ingestion。即使模型名稱相同，實際服務仍需驗證模型版本、維度與 Tokenizer。匯出不包含 Chunk／向量資料，切換到自己的 ES／MongoDB 需準備資料或重新 Ingestion。

YAML 仍使用示例 Engine Image；Local Search 固定單一副本，Ingestion／Inference 共用程序。Secret 以引用／Volume 掛載呈現，Runtime 解析是待實作契約。未部署、不建立真實 DB、不送出任何模型 API 呼叫。



## 14. 2026-10-14：共用 LLM 清單與模組化檢查訊息（v0.5）

### 14.1 LLM 服務設定集中管理

Create／Edit Config 工具列新增「LLM 服務設定」。目前作用域是每個 RAG System 的配置清單；不是跨 Workspace 自動共享的全域服務目錄。

- 每筆服務有穩定 id、可修改的顯示名稱、DEV test use／OpenAI-compatible API，以及自己的 URL、Model ID、認證引用、Timeout。
- Query Transformation 與 Generation 透過 llm_ref 引用，可使用同一個 LLM，也可各自選不同的 LLM。
- 模組內不重複出現 URL、認證與 Model ID；只有下拉選單和「管理 LLM」入口。
- Embedding 與 Rerank 的任務與 API 契約不同，維持各自連線設定。
- 服務名稱需非空且唯一。刪除使用中的服務不自動替換，保留失效引用並阻止儲存，提示受影響模組重新選擇。
- 修改被引用的連線／模型設定會影響對應 Inference 模組，不需重新 Ingestion；修改未使用服務不觸發重建。
- 有效配置與部署匯出只包含使用中的 LLM。同一個服務由兩個模組使用時，部署資源表只顯示一次；llm_ref 仍指向同一穩定 ID。

配置概念：

```json
{
  "llms": [
    {"id": "llm-default", "name": "Default LLM", "mode": "DEV test use", "model": "demo-chat"}
  ],
  "transform": {"method": "Rewrite", "llm_ref": "llm-default"},
  "generation": {"llm_ref": "llm-default"}
}
```

上例僅展示引用關係，省略 Prompt 與其他必填模組參數；不是可直接執行的完整 Config。

### 14.2 Query Transformation 自訂 Prompt

Rewrite／Multi-query 分別保留自己的 Prompt 草稿，切換方法不覆蓋。None 停用模型與 Prompt，不納入有效執行配置。

| 方法 | 支援的變數 | 必填變數 | 輸出約定 |
|---|---|---|---|
| Rewrite | query | query | 一個非空改寫問題 |
| Multi-query | query、count | query、count | count 個衍生問題，第一版以每行一個文字問題示意 |

UI 提供變數插入與替換後的預覽。空 Prompt、未知變數及缺少必要變數會阻止儲存。只執行單次變數替換，不執行程式碼。

原始問題永遠保留；是否額外加入搜尋由 include_original 決定，不交給 Prompt 判斷。Runtime 仍需驗證輸出問題非空、數量合法，處理模型未遵守格式的情況；prototype 不呼叫 LLM。

### 14.3 檢查訊息標註模組

下方 Validator、AI 設定建議中的驗證結果與匯出檢查使用方括號前綴，例如：

```text
[Chunking] Overlap 必須小於 Chunk Size。
[Query Transformation] Prompt 需包含 {{query}}。
[Retrieval] 向量欄位：summary_vector 不在上游，請修正。
[Rerank] Top-N 必須介於 1 與 Retrieval Top-K。
[Generation] LLM 選擇已失效，請重新選擇。
[LLM Settings / Default LLM] 請填入有效服務 URL。
```

相依錯誤以需要修正的模組為主：例如 Indexing 移除向量後，Retrieval 的失效選擇標註 [Retrieval]。共用 LLM 設定不完整時，同時提示共用服務及受影響模組。

