# Document、QueryContext 與索引交接

## Document

Import、Parsing、Chunking、Embedding、Indexing 與檢索候選共用 [Document](../schemas/document.schema.json)。Builder 依各階段的有效設定細化 `structdata` 與 `vectors`，並與 Engine 共用同一套邊界驗證規則。

一筆 `Document` 可以代表原始文件、解析單位或切片。由同一來源產出的多筆 `Document` 共用 `document_id`，切分後以 `data_id` 區分各筆。

Elasticsearch 索引存取層另在每筆 ES Chunk 保存內部 `write_id`，同一次文件寫入的 Chunk 共用此值。它與 `source_revision` 分開，也不屬於共用 `Document` 或 Remote API 契約。ES `_id` 的衍生及清理範圍見 [Elasticsearch 文件覆寫](06_runtime_api_and_deployment.md#elasticsearch-document-replacement)。

| 欄位 | 責任與語意 |
|---|---|
| `document_id` | 原始文件穩定識別。多頁、多切片保留原文件 ID。外部候選也需填可辨識來源的 ID。 |
| `source_revision` | 選填的來源文件版本。接受字串（含 `""`）與 `null`。匯入時有帶值，解析單位、Chunk 與檢索候選原樣保留。匯入時省略，下游維持省略。同一 System 以 `document_id` 判斷覆寫。文件清單只彙整非空版本字串。 |
| `data_id` | 每筆可檢索 Document 的識別，Chunking 產出後必填。不同切片可共用 document_id，data_id 須能區分它們。去重使用 data_id，文件分組及刪除使用 document_id。 |
| `structdata` | 平面業務欄位，依 [Data Meta Schema](#data-meta-schema) 宣告型別、必填性與搜尋能力。 |
| `content` | 待解析來源，`media_type` 加 `uri` 或 `base64` 二選一。與已知 structdata 可並存。 |
| `metadata` | 選填 JSON object，可含巢狀值。整包傳遞、儲存與回傳，子欄位不參與檢索、Filter、分組、文字處理或計算。選填的 `_rag` 可附帶平台追溯資訊。 |
| `vectors` | 名稱到 DenseVector 的物件。每筆向量含 `values`、`embedding_profile_id`、`source_field`。 |

共用外層只要求 `document_id`。Import 依設定決定是否要求 `content`、`structdata` 及其欄位。檢索候選額外必須提供 `data_id`、`structdata`，詳細欄位由有效 System Schema 決定。`content.media_type` 指定來源格式，`uri` 引用可取得的來源，`base64` 承載同一來源的編碼內容。

<a id="data-flow"></a>
## 各階段有效 Schema

| 邊界 | 輸入 | 輸出與規則 |
|---|---|---|
| Import | [Ingestion Request](../schemas/ingestion_request.schema.json) | `documents` 非空，Runtime 預檢後拆成逐文件工作。每筆資料用 Import 宣告的 Document Schema，共用參數留在執行環境。 |
| Parsing | 單筆 Document | `Document[]`，結構化資料可直傳。選一種內建檔案解析方法時，保留原欄位並輸出 `structdata.contenttext`。Remote 依宣告產出欄位。 |
| Chunking | 同份文件的 `Document[]` | `Document[]`，各筆加 `data_id`。選單一 structdata 字串欄位切分，可另複製其他欄位並繼承合法 metadata。逐 Unit 切分，overlap 不跨 Unit。 |
| Embedding | 切分後 `Document[]` | 保留資料識別及有效內容，附上宣告的 vectors。內建可先組合已知文字欄位，按有效欄位映射產向量。 |
| Indexing | 可檢索 `Document[]` | 沿用欄位型別與必填性，可覆寫 `searchable`／`filterable`。定稿候選 Schema 與平台索引的 IndexBinding。 |
| Inference | `QueryContext[]` | 候選 `ResultItem.data` 遵守 System 有效的可檢索 Document Schema。 |

Import 結構化來源示例為 `{"document_id":"p-1","structdata":{"title":"維護指南","text":"定期清潔"}}`。檔案來源以 content 提供原檔，已知 title 等欄位仍可放 structdata。Parser 消費 content 並輸出可供下游處理的 structdata；Schema 版本與所選解析方法取自 Config。

Chunking 逐 Unit 處理同一個選定欄位，可另外保留該欄位的原文 Document。已有完全相同的切片時沿用該筆。重建時，文件更新、舊切片清除、失敗原子性及重試遵守 Runtime 規格。追溯資訊可依所選方法附在 metadata。

<a id="data-meta-schema"></a>
## Data Meta Schema 欄位總表

[Data Meta Schema](../schemas/data_meta.schema.json) 定義每個 `structdata` 欄位可設定的屬性。欄位名是 `structdata` 下的平面 key。用於 Filter、全文欄位選擇與分組的引用寫成 `structdata.<欄位名>`。

| 可設定屬性 | 宣告時的值 | Indexing 最終調整 | 意義 |
|---|---|---|---|
| `type` | 必填，使用下表的型別 | 沿用 | 驗證資料值、決定可選用途及 Filter 運算子 |
| `required` | 必填，`true`／`false` | 沿用 | `true` 要求欄位存在。選填可以省略；提供時須符合型別，`null` 無效 |
| `searchable` | 布林，省略為 `false` | 可逐欄覆寫 | `true` 建立全文搜尋能力，首版僅 `string` 可開啟 |
| `filterable` | 布林，省略為 `false` | 可逐欄覆寫 | `true` 開放該欄位按型別支援的運算子過濾 |

| `type` | 合法資料值範例 | 全文 `searchable` | `filterable: true` 的運算子 | `group_by` | 切分、Embedding／Rerank 文字來源 |
|---|---|---|---|---|---|
| `string` | `"製造部"` | 可開啟 | `eq`、`in` | 可 | 可，仍須滿足元件的必填等條件 |
| `string_array` | `["AI", "ML"]` 或 `[]` | — | `eq`、`in`，比對陣列元素 | — | — |
| `integer` | `12` | — | `eq`、`in`、`gt`、`gte`、`lt`、`lte` | — | — |
| `number` | `300.5`，有限數值 | — | `eq`、`in`、`gt`、`gte`、`lt`、`lte` | — | — |
| `boolean` | `true` | — | `eq`、`in` | — | — |
| `date` | `"2026-11-16"`，日曆日期 | — | `eq`、`in`、`gt`、`gte`、`lt`、`lte` | — | — |
| `datetime` | `"2026-11-16T09:30:00+08:00"`，精確到秒 | — | `eq`、`in`、`gt`、`gte`、`lt`、`lte` | — | — |

平台自帶的 `document_id` 也可用於 `group_by`。所有型別都可保存、回傳與依 Component 設定複製。`string_array` 是首版唯一集合型別，元素皆為字串，必填欄位仍接受 `[]`。`datetime` 要帶 `Z` 或 `±HH:MM`，由 Engine 按 UTC 時間點比較。Builder 預設以 `Asia/Taipei` 顯示及輸入。`date` 直接使用 `YYYY-MM-DD`。

推導從 Import 宣告入口欄位開始。各 Module 依實際輸出保留、產生、改名、轉型或移除欄位。保留及複製欄位繼承宣告；若實際保證補值或轉型，產生該輸出的 Module 宣告新 `required` 或 `type`。例如 Parsing 將選填 `price` 補成每筆都有，後續可使用必填的 `price`。Indexing 只覆寫搜尋能力，並依最終設定建立索引及定稿 `ResultItem.data` 的 `Document` 契約。Remote-only 的查詢依同一份已編譯的候選契約驗證，無須建立平台索引。

<a id="filter-semantics"></a>
### Filter 形狀與語意

- `filters` 為陣列，外層條件以 `AND` 組合。元素是 `{field, operator, value}` 或 `{any: [...]}`。`any` 內是非空的單層條件清單，任一命中即可。
- `eq` 接單一值，`in` 接非空值陣列。值依有效 `type` 嚴格驗證。字串採精確比對，保留大小寫及空白；數值欄位的 `300` 與字串 `"300"` 有不同型別。`string_array` 採元素比對，例如 `["AI", "ML"]` 命中 `eq "AI"` 與 `in ["ML", "NLP"]`。
- 缺欄位與空陣列均不命中該條件。Filter 的 `null` 和 `in []` 回驗證錯誤。可用 `gte` 搭配 `lt` 表示半開區間，例如台灣時間一整天的起點 `2026-11-16T00:00:00+08:00` 與終點 `2026-11-17T00:00:00+08:00`。
- 固定 Filter 在發布 Config 時驗證，動態 Filter 在收到請求時驗證。Engine 合併兩組條件為 `AND`，再放入 `QueryContext.filters`。內建 Retrieval 各路先過濾再取 Top-K。Remote Retrieval 收到共用 I/O，過濾、排序及截斷方式由外部服務決定。

## 向量與 Profile

每個向量欄位對應來源欄位、維度及 Embedding Profile。values 的元素為有限數字且數量等於宣告維度。同 Profile 的維度一致。Indexing 與內建向量 Retrieval 使用相容的文件／Query Encoder。向量維度相同只滿足形狀檢查，模型及輸入處理仍須落在相容的向量空間。Remote 包到 Embedding 時，由 User 宣告輸出向量欄位，內建向量 Retrieval 依 Profile 設定 Query Encoder。

<a id="inference-contract"></a>
## QueryContext／ResultSet／ResultItem

[QueryContext[]](../schemas/query_context.schema.json) 是 Query Transformation、Retrieval、Rerank 的共用 I/O，也是 Runtime Inference 成功回應。每份 Context 有 `ori_query`、`query`、`filters`、`result_sets`、`metadata`。每個 ResultSet 以 `key` 表示搜尋路徑或群組，`items` 的順序代表排名。`ResultItem.data` 必填，值為候選 `Document`，`score` 選填。無命中時回空候選。

| 欄位 | 建立與使用方式 |
|---|---|
| `ori_query` | Inference Input 帶入原始 `query`。改寫後的 Context 都保留它。 |
| `query` | 此 Context 使用的實際查詢文字。未改寫時等於 `ori_query`。 |
| `filters` | 已驗證並合併的固定與動態 Filter，沒有條件時為 `[]`。 |
| `result_sets` | Inference Input 初始化為 `[]`，Retrieval 填入有序候選清單。內建 Retrieval 無命中仍保留一個 ResultSet，其 `items` 為 `[]`。 |
| `metadata` | 沿用 Request 的 Query metadata，省略時為 `{}`。Document 自身的 metadata 仍放在候選裡。 |

- Query Transformation 可產生多個 Context，保留原始問題、條件與 Query metadata。
- 內建 Retrieval 對每個 Query 交付一份 ResultSet，多路搜尋先融合再交付，無命中時 items 為空。ResultSet key 在同一 Context 內唯一，同一清單的 data_id 唯一。
- Rerank 對輸入候選評分、重排與裁切，保留候選識別與 Document。融合以 `data_id` 對齊候選；`group_by` 使用候選 Document 的選定欄位保留目前排名最高的代表。組合多節點的 Remote API 依區段邊界驗證。
- `QueryContext.filters` 沿用 [Filter 形狀與語意](#filter-semantics)。Engine 依候選欄位與搜尋能力驗證，欄位、運算子或值失效時回報錯誤。
- 成功回應代表當次所需的查詢與搜尋路徑均完成。路徑失敗時回傳整次 Inference 錯誤，詳見 [Runtime Inference](06_runtime_api_and_deployment.md#src-21-5-inference)。

**外部 Retrieval 的候選 Schema 仍由 System 的 Ingestion 設定推導。** 例如 System 的有效候選欄位有必填字串 `structdata.title`、`structdata.text`，外部商品 API 回傳的候選也要有這些欄位。後段內建 Rerank 因而能選用 text。外部資料可直接查詢，平台只需已驗證的有效 Schema，無須先執行 Ingestion 或建立平台索引。

## IndexBinding

[IndexBinding](../schemas/index_binding.schema.json) 是平台管理索引的執行交接。第一版每個 System 至多一組平台邏輯索引。Indexing 提供格式、定位與能力，Engine 驗證綁定，內建 Retrieval 由執行環境取得。多個索引欄位與後端內部索引屬同一組綁定。

| 欄位 | 必填 | 語意 |
|---|---|---|
| `artifact_type` | 是 | 指定受註冊的索引格式與版本，由 Engine 判斷 Retrieval 是否相容。 |
| `target` | 依實作 | 供該索引實作定位實體資料的物件。欄位由對應 Adapter 定義。 |
| `fulltext_fields` | 否 | 已綁定全文索引的欄位，以 `structdata.<欄位名>` 表示。 |
| `filter_fields` | 否 | 已綁定過濾能力的欄位，採同一引用格式。 |
| `vector_bindings` | 否 | 以向量名稱為 key，每筆包含 `source_field`、`embedding_profile_id`、`dimensions`。Retrieval 依此選擇相容的 Query Encoder。 |

省略能力清單或映射時，編譯器視為空集合。有效 IndexBinding 仍須符合 System 的索引計畫與 Adapter 格式要求。可驗證的例子見 [Local Search IndexBinding](../examples/system_config/index_binding.example.json)。

外部 Remote Retrieval 由服務管理其資料及搜尋，平台用 System Document Schema 驗證候選。平台的文件查詢、清單及刪除以平台所管理的資料為作用範圍。相關工作狀態與 API 見 [Runtime](06_runtime_api_and_deployment.md)。

## 範例與相容

[現行 JSON／Python 驗證](../examples/user_remote_api/README.md) 涵蓋批次匯入、Remote Parsing 到 Embedding 及外部 Retrieval。三份舊文件型別與舊 ResultItem.chunk 供[歷史案例](history/superseded/2026-11-11_developer_mode.md)重現。
