# Document、QueryContext 與索引交接

## Document

Import、Parsing、Chunking、Embedding、Indexing 與檢索候選共用 [Document](../schemas/document.schema.json)。各階段依有效設定補上必填欄位與可接受型別。JSON Schema 的共用外層供重用，Builder 以 System 的有效欄位規格細化 `structdata`、索引／過濾用的 metadata 路徑及 `vectors`。

一筆 `Document` 可以代表原始文件、解析單位或切片。由同一來源產出的多筆 `Document` 共用 `document_id`，切分後以 `data_id` 區分各筆。

Elasticsearch 索引存取層另在每筆 ES Chunk 保存內部 `write_id`，同一次文件寫入的 Chunk 共用此值。它與 `source_revision` 分開，也不屬於共用 `Document` 或 Remote API 契約。ES `_id` 的衍生及清理範圍見 [Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。

| 欄位 | 責任與語意 |
|---|---|
| `document_id` | 原始文件穩定識別。多頁、多切片保留原文件 ID。外部候選也需填可辨識來源的 ID。 |
| `source_revision` | 來源版本，與 Config Revision、索引版本分開。入口可省略，Runtime 於下游使用已解析的版本。預設版本生成與衝突政策見 Q-007／008。 |
| `data_id` | 每筆可檢索 Document 的識別，Chunking 產出後必填。不同切片可共用 document_id，data_id 須能區分它們。去重使用 data_id，文件分組及刪除使用 document_id。 |
| `structdata` | 平面純量欄位，支援字串、整數、有限數字、布林。名稱、型別、必填性由有效 Schema 決定，選填可缺省。 |
| `content` | 待解析來源，`media_type` 加 `uri` 或 `base64` 二選一。與已知 structdata 可並存。 |
| `metadata` | 可含巢狀 JSON。作索引或過濾的路徑需宣告型別。追溯 `_rag` 選填，平台保留欄位由 Runtime 管理。文件級 ACL 延後討論。 |
| `vectors` | 名稱到 DenseVector 的物件。每筆向量含 `values`、`embedding_profile_id`、`source_field`。 |

<a id="data-flow"></a>
## 各階段有效 Schema

| 邊界 | 輸入 | 輸出與規則 |
|---|---|---|
| Import | [Ingestion Request](../schemas/ingestion_request.schema.json) | `documents` 非空，Runtime 預檢後拆成逐文件工作。每筆資料用 Import 宣告的 Document Schema，共用參數留在執行環境。 |
| Parsing | 單筆 Document | `Document[]`，結構化資料可直傳。選一種內建檔案解析方法時，保留原欄位並輸出 `structdata.contenttext`。Remote 依宣告產出欄位。 |
| Chunking | 同份文件的 `Document[]` | `Document[]`，各筆加 `data_id`。選單一 structdata 字串欄位切分，可另複製其他欄位並繼承合法 metadata。逐 Unit 切分，overlap 不跨 Unit。 |
| Embedding | 切分後 `Document[]` | 保留資料識別及有效內容，附上宣告的 vectors。內建可先組合已知文字欄位，按有效欄位映射產向量。 |
| Indexing | 可檢索 `Document[]` | 保存有效欄位，設定全文、向量及精確過濾的索引路徑。平台管理的索引以 IndexBinding 銜接。 |
| Inference | `QueryContext[]` | 候選 `ResultItem.data` 遵守 System 有效的可檢索 Document Schema。 |

Import 結構化來源示例為 `{"document_id":"p-1","structdata":{"title":"維護指南","text":"定期清潔"}}`。檔案來源以 content 提供原檔，已知 title 等欄位仍可放 structdata。Parser 消費 content 並輸出可供下游處理的 structdata；Schema 版本與所選解析方法取自 Config。

Chunking 逐 Unit 處理同一個選定欄位，可另外保留該欄位的原文 Document。已有完全相同的切片時沿用該筆。重建時，文件更新、舊切片清除、失敗原子性及重試遵守 Runtime 規格。追溯及 metadata 處理提示依所選方法支援。

## 向量與 Profile

每個向量欄位對應來源欄位、維度及 Embedding Profile。values 的元素為有限數字且數量等於宣告維度。同 Profile 的維度一致。Indexing 與內建向量 Retrieval 使用相容的文件／Query Encoder。向量維度相同只滿足形狀檢查，模型及輸入處理仍須落在相容的向量空間。Remote 包到 Embedding 時，由 User 宣告輸出向量欄位，內建向量 Retrieval 依 Profile 設定 Query Encoder。

<a id="inference-contract"></a>
## QueryContext／ResultSet／ResultItem

[QueryContext[]](../schemas/query_context.schema.json) 是 Query Transformation、Retrieval、Rerank 的共用 I/O，也是 Runtime Inference 成功回應。每份 Context 有 `ori_query`、`query`、`filters`、`result_sets`、`metadata`。每個 ResultSet 以 `key` 表示搜尋路徑或群組，`items` 的順序代表排名。`ResultItem.data` 必填，值為候選 `Document`，`score` 選填。無命中時回空候選。

- Query Transformation 可產生多個 Context，保留原始問題、條件與 Query metadata。
- 內建 Retrieval 對每個 Query 交付一份 ResultSet，多路搜尋先融合再交付，無命中時 items 為空。ResultSet key 在同一 Context 內唯一，同一清單的 data_id 唯一。
- Rerank 對輸入候選評分、重排與裁切，保留候選識別與 Document。融合以 `data_id` 對齊候選；`group_by` 使用候選 Document 的選定欄位保留目前排名最高的代表。組合多節點的 Remote API 依區段邊界驗證。
- 內建路徑依有效設定合併固定過濾、請求 filters 與已綁定參數。精確 Filter 使用欄位路徑與 `eq`／`in`，依宣告型別檢查。Remote Retrieval 使用自己的服務參數與搜尋邏輯，保留 QueryContext 的 filters，外部服務負責其資料存取規則。
- 成功回應代表當次所需的查詢與搜尋路徑均完成。路徑失敗時回傳整次 Inference 錯誤，詳見 [Runtime Inference](06_runtime_api_and_deployment.md#src-21-5-inference)。

**外部 Retrieval 的候選 Schema 仍由 System 的 Ingestion 設定推導。** 例如 System 的有效候選欄位有必填字串 `structdata.title`、`structdata.text`，外部商品 API 回傳的候選也要有這些欄位。後段內建 Rerank 因而能選用 text。外部資料可直接查詢，平台只需已驗證的有效 Schema，無須先執行 Ingestion 或建立平台索引。

## IndexBinding

[IndexBinding](../schemas/index_binding.schema.json) 是平台管理索引的執行交接。第一版每個 System 至多一組平台邏輯索引。Indexing 提供格式、定位與能力，Engine 驗證綁定，內建 Retrieval 由執行環境取得。多個索引欄位與後端內部索引屬同一組綁定。

外部 Remote Retrieval 由服務管理其資料及搜尋，平台用 System Document Schema 驗證候選。平台的文件查詢、清單及刪除以平台所管理的資料為作用範圍。相關工作狀態與 API 見 [Runtime](06_runtime_api_and_deployment.md)。

## 範例與相容

[現行 JSON／Python 驗證](../examples/user_remote_api/README.md) 涵蓋批次匯入、Remote Parsing 到 Embedding 及外部 Retrieval。三份舊文件型別與舊 ResultItem.chunk 供[歷史案例](history/superseded/2026-11-11_developer_mode.md)重現。
