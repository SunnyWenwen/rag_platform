# RAG Platform — 資料契約與索引設計討論結論

> 2026-10-13 · 設計草案 v0.3
>
> 整理本輪 Import／Parsing／Chunking／Embedding／Indexing／Retrieval 討論。這是設計規格，不代表 Engine 或 UI 已實作。
> 本文取代《04_module_methods_io_contracts.md》v0.2 中關於 ParsedDocument、Chunk、獨立 VectorSet、多欄位與搜尋後端的舊提案；其他模組的執行、錯誤與評估契約仍沿用原文件。

## 1. 決策狀態

| 項目 | 結論／狀態 |
|---|---|
| 統一資料物件 | ParsedDocument 五個頂層 key；Chunk 六個頂層 key，新增 vectors |
| 模組分工 | Parsing 擷取及映射；Chunking 切分及繼承；Embedding 產生向量；Indexing 儲存及建索引 |
| 多欄位 | 可分別選擇 Embedding、Indexing、Retrieval、Rerank、Generation 使用的欄位 |
| 搜尋後端 | ES 已選定；第二個後端建議 Local Search（FAISS＋BM25），尚待實作驗證 |
| 持久化 | Local Search 支援 Memory／MongoDB 的設計方向；MongoDB 不執行該模式的向量搜尋 |
| 使用介面 | 後端共用設定流程，能力差異以顯示但停用及原因說明處理 |
| Hybrid | 第一版建議 RRF；正規化後加權分數融合為後續選項 |
| 第一版切分 | 建議一個主要切分欄位＋多個複製欄位 |
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
- size／overlap／length_unit：明確指定字元或 token 與 tokenizer。

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

第一版建議 RRF，逐路 Top-K 與融合後候選 Top-K 分開定義。ES 需配置查詢及融合；不是建好索引就自動 Hybrid。Local Search 由平台負責 BM25、FAISS 結果融合。

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
3. Local Search 第二後端及其 Hybrid 是否全部納入首版交付。
4. metadata 的保留欄位、ACL 與 filter 實作。
5. 缺欄位處理、文件／Chunk ID 規則與來源更新策略。
6. 文件分組的預設位置、每文件片段數與評估方式。
7. MongoDB 的索引版本、恢復流程及更新／刪除一致性。
8. 是否保留原始檔及 ParsedDocument，供重新 Ingestion 使用。

本次整理未修改 UI 或實作 Engine。實作時須同步更新舊 Contract 與 Registry，避免仍使用 Chunk.text、獨立 VectorSet 或單一向量 Profile 假設。

## 12. 官方參考

以下供實作驗證能力使用；本文的資料物件與配置是平台自訂設計。

- Elasticsearch 欄位型別：https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/field-data-types
- Elasticsearch Dense vector：https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector
- Elasticsearch RRF Retriever：https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rrf-retriever
- Elasticsearch Collapse：https://www.elastic.co/docs/reference/elasticsearch/rest-apis/collapse-search-results
- FAISS 索引讀寫：https://github.com/facebookresearch/faiss/wiki/Index-IO%2C-cloning-and-hyper-parameter-tuning
- LangChain FAISS 整合：https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/vectorstores/faiss.py
