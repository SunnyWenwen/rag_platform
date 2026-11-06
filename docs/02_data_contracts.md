# 共用資料契約與連續範例

## 閱讀目錄

- [資料流與單一來源](#資料流與單一來源)
- [情境整理與分類總覽（報告摘要）](#src-13-0-情境整理與分類總覽報告摘要)
- [已確認方向與責任](#src-13-1-已確認方向與責任)
- [單筆文件 JSON Schema](#src-13-2-單筆文件-json-schema)
- [輸入範例](#src-13-3-輸入範例)
- [是否也是 Parser 的 Input？](#src-13-4-是否也是-parser-的-input)
- [Parser 能力與 Chunker 相容](#src-13-5-parser-能力與-chunker-相容)
- [驗證邊界與待決事項](#src-13-6-驗證邊界與待決事項)
- [ParsedDocument：情境與分類結果（報告摘要）](#src-14-0-情境與分類結果報告摘要)
- [ParsedDocument：唯一共用 Schema](#src-14-1-唯一共用-schema)
- [ParsedDocument：Parser 與 Chunker 分工](#src-14-2-parser-與-chunker-分工)
- [ParsedDocument：來源追溯與欄位傳遞](#src-14-3-來源追溯與欄位傳遞)
- [ParsedDocument：取捨與驗收](#src-14-4-取捨與驗收)
- [ParsedDocument：Parser 相容性與驗證範圍](#src-14-5-parser-相容性與驗證範圍)
- [Chunk：情境與結果摘要](#src-15-0-情境與結果摘要)
- [Chunk：共用物件](#src-15-1-共用物件)
- [Chunk：切分與欄位映射](#src-15-2-切分與欄位映射)
- [Chunk：來源追溯（Component 選用）](#src-15-3-來源追溯component-選用)
- [Chunk：metadata、向量與下游](#src-15-4-metadata向量與下游)
- [Chunk：有效切分設定與 fingerprint（選用參考工具）](#src-15-5-有效切分設定與-fingerprint選用參考工具)
- [Chunk：Chunk ID、序號與重建](#src-15-6-chunk-id序號與重建)
- [Chunk：後續確認與欄位組裝（D-53，2026-11-03 已確認功能方向）](#src-15-9-後續確認與欄位組裝d-532026-11-03-已確認功能方向)
- [Inference：QueryContext／ResultSet／ResultItem](#src-05-46-querycontextresultsetresultitem已確認的簡化-contract)
- [FilterCondition 與條件合併](#src-05-65-過濾條件)
- [IndexBinding：決策與責任](#src-19-1-決策與責任)
- [IndexBinding：共用 Schema](#src-19-2-共用-schema)
- [IndexBinding：索引格式定義與 Developer 配套](#src-19-3-索引格式定義與-developer-配套)
- [IndexBinding：範例](#src-19-4-範例)
- [IndexBinding：狀態、保存與待決邊界](#src-19-5-狀態保存與待決邊界)
- [IndexBinding：D-58：文件存在／清單與直接刪除](#src-19-6-d-58文件存在清單與直接刪除)
- [Python／Pydantic：完整連續範例](#src-17-2-逐型別範例)
- [Python 推論根物件與呼叫方式](#src-17-3-推論直接傳-list)
- [資料測試、重現方式與限制](#src-17-4-驗證與限制)
- [Schema 與業務欄位的責任](#schema-與業務欄位的責任)

- [Embedding Profile 與 Document／Query 配對](#embedding-profile)

- [ParsedDocument 格式遷移](#parsed-document-migration)

- [契約重現與文件產生工具](#contract-test-commands)


更新：2026-11-05。這是 A 的資料形狀與語意主責文件；機器來源在 schemas/，可執行型別在 examples/pydantic_contracts。B 的欄位細化與 D 的參數不在此另定一份。

## 資料流與單一來源

| 邊界 | 資料 | 機器來源 |
|---|---|---|
| API item／Import→Parser | IngestionDocument；API 外層為非空 List | [Schema](../schemas/ingestion_document.schema.json) |
| Parser→Chunker | ParsedDocument 清單；四鍵、平面 units | [Schema](../schemas/parsed_document.schema.json) |
| Chunker→Embedding→Indexing | Chunk 清單；六鍵，同一物件補 vectors | [Schema](../schemas/chunk.schema.json) |
| Query Transformation→Retrieval→Rerank | QueryContext[]；ResultSet／ResultItem 置於其中 | [Schema](../schemas/inference_context.schema.json) |
| Indexing→Retrieval | 單一 IndexBinding，透過可信 Context 取得 | [Schema](../schemas/index_binding.schema.json) |

原始輸入、Parser 輸出與 Chunk 的格式分開；不回到已取消的 structure／ParsedDocument.fields／InferenceState。Unit 數、Chunk 數或文字內容不同不等於 Schema 改變。

<a id="src-13-0-情境整理與分類總覽報告摘要"></a>
## 情境整理與分類總覽（報告摘要）

**這份文件整理的是「各種來源的資料，如何透過同一個入口交給 Retrieval Engine Library」**。使用者可以送簡單文字、結構化紀錄、原始文件，或已被其他工具解析好的內容；平台統一接收 JSON，由相容 Parser 處理，不要求所有呼叫端先完成同樣程度的解析。

<a id="src-13-01-從哪些使用情境整理而來"></a>
### 從哪些使用情境整理而來

| 使用情境 | 輸入方式與例子 | 誰負責處理 |
|---|---|---|
| 直接送一段文字 | content 是文字，例如操作說明 | 相容文字 Parser 驗證並產生 ParsedDocument |
| 一筆資料有多個內容欄位 | content 是 JSON object，包含原文、標題、已有摘要等；不是多筆文件 | 相容 Structured JSON Parser／Adapter 轉成內容欄位，後續模組另選欄位用途 |
| 在 Builder 上傳 CSV 測試 | 每列映射為一筆 JSON，分清內容與 metadata | Builder 做欄位映射與傳輸轉換，再呼叫相同 API |
| 傳入 PDF／PPTX／Excel／圖片等原始檔 | 用 base64 帶檔案，或用 uri 指向可存取資源 | SDK 共用能力取得／解碼，具有對應能力的 Parser 再解析 |
| 透過 URL 傳入資料 | uri 可指向文字、JSON 或原始檔；URL 不是文件格式 | 平台取得內容，再依格式與能力選 Parser；不自動代表網站爬取 |
| 上游已完成解析 | content 內含頁面、段落、切分標註，或 Docling／MinerU 原生結果 | 相容 Adapter 驗證與正規化，避免重做原始檔解析；原生格式不直接等於 ParsedDocument |
| 同一個 System 接收多種資料 | 文字、PDF、已解析 JSON 等混合使用 | 啟用多個 Parser 並依能力自動路由；重疊時才需預設策略／profile |
| 自行部署後由業務系統串接 | 呼叫端自行讀檔／轉換，再送 JSON | 不需部署 Builder；仍使用相同 Engine 輸入契約與解析流程 |

<a id="src-13-02-分類結果傳入方式內容格式處理程度分開看"></a>
### 分類結果：傳入方式、內容格式、處理程度分開看

| 分類維度 | 分類結果 | 對設計的影響 |
|---|---|---|
| **怎麼取得內容** | content 直接內容／base64 編碼檔案／uri 資源引用，三選一 | 決定直接讀取、解碼或下載，不決定要用哪個解析演算法 |
| **內容是什麼格式** | 文字、JSON、PDF、PPTX、Excel、圖片等 | 依 media_type、必要 schema_id 及實際內容，驗證是否有相容 Parser |
| **已經處理到哪一步** | 未解析內容／上游已解析內容 | 前者解析來源；後者驗證與轉換，不強迫全部重新解析 |

三個維度可以組合，例如「透過 URL 提供已解析 JSON」或「用 Base64 提供原始 PDF」。多個 Parser 的用途是提供相容路徑，不是讓每筆資料依序執行全部 Parser。API 及 Parser 共用 IngestionDocument；內容取得使用 SDK 共用資源，不另維護第二份輸入 Schema。

<a id="src-13-021-content直接傳文字"></a>
<a id="src-13-022-content直接傳多欄位-json"></a>
<a id="src-13-023-base64傳送編碼後的檔案內容"></a>
<a id="src-13-024-uri取得-url-指向的檔案"></a>
<a id="src-13-025-content上游已整理好的-units"></a>
<!-- classification-examples:ingestion:start -->

以下是符合目前 IngestionDocument 外層 Schema 的單筆例子，與 Parser Input 使用同一份契約。例子由 [共用資料來源及產生工具](../examples/contracts/render_classification_examples.py) 驗證／產生，資料見 [report_cases.json](../examples/contracts/report_cases.json)；此處驗證資料形狀，尚未執行 API。

#### content：直接傳文字

只有文件 ID 與內容即可表達最簡單情境；相容 Parser 產生 ParsedDocument。

```json
{
  "document_id": "manual-001",
  "content": "清潔前先斷電。"
}
```

#### content：直接傳多欄位 JSON

這是一筆文件的原文、標題與既有摘要；metadata 另外保存部門。CSV 映射後也可形成這種單筆資料。

```json
{
  "document_id": "manual-001",
  "content": {"text": "清潔前先斷電。", "title": "設備手冊", "summary": "清潔前的安全步驟"},
  "metadata": {"department": "engineering"}
}
```

#### base64：傳送編碼後的檔案內容

用短文字檔示範 Base64，實際可解碼為「清潔前先斷電。」。PDF／PPTX／Excel 使用相同傳輸欄位，須填入完整檔案內容、正確 media_type 並有相容 Parser。

```json
{
  "document_id": "manual-file-001",
  "base64": "5riF5r2U5YmN5YWI5pa36Zu744CC",
  "media_type": "text/plain"
}
```

#### uri：取得 URL 指向的檔案

只傳資源位置，由共用能力取得 PDF，再交給相容 Parser；這個示意網址未進行下載／連線驗證。

```json
{
  "document_id": "report-001",
  "uri": "https://storage.example.com/report.pdf",
  "media_type": "application/pdf"
}
```

#### content：上游已整理好的 Units

content.units 是平面的內容單位列表，由相容 Adapter 驗證後與外層 ID／版本／metadata 組成 ParsedDocument。schema_id 是需註冊的示意識別；不是任何 Parser 都自動支援。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "schema_id": "example.preparsed-units/0.2-draft",
  "content": {
    "units": [
      {"text": "## 帳號申請\n填寫申請單，送交主管核准。", "section_title": "帳號申請", "page": 1},
      {"text": "## 密碼重設\n使用公司信箱申請重設密碼。", "section_title": "密碼重設", "page": 2}
    ]
  },
  "metadata": {"filename": "manual.pdf"}
}
```

上述五例都符合共同外層；media_type／schema_id 能省略的條件仍依正文。對應的 Parser／服務能力必須另外具備，範例通過 Schema 不代表 Runtime 已實作。

<!-- classification-examples:ingestion:end -->

<a id="src-13-03-責任分工與目前範圍"></a>
### 責任分工與目前範圍

| 層級 | 責任 |
|---|---|
| Retrieval Builder／自行部署的呼叫端 | 提供方便的上傳／映射／檔案傳輸轉換；組成 JSON |
| Engine 的共用入口／SDK 資源能力 | 驗證共同外層、授權取得內容、解碼及必要限制；路由到已設定的 Parser |
| Parser／Adapter | 理解來源或轉換已解析資料，產出統一 ParsedDocument，詳見 [ParsedDocument：的情境與結構分類](#src-14-1-唯一共用-schema) |

JSON-only、扁平輸入、三種來源、API／Parser 共用契約與多 Parser 路由方向已確認；API／SDK 尚未實作，實際格式需有相容 Component 才可執行。單筆外層 Schema 與 D-58 的 List 接收格式已確認；D-64 的 Runtime 初始大小／文件數限制已集中在 22；來源版本生成、逐 Provider／Client 限制與正式供應者支援仍依正文核定。直接匯入最終 Chunk／vectors 另外討論，不混入「上游已解析」的支援承諾。

<a id="src-13-1-已確認方向與責任"></a>
## 已確認方向與責任

- Engine Runtime 的 Ingestion API 只接收 JSON body。Retrieval Builder 可提供文件／CSV 上傳及轉換；自行部署的呼叫端自行完成相同傳輸前處理，不要求部署 Builder。
- JSON 支援 inline 文字／物件、Base64 檔案與資源 URI。傳輸前處理不等於語意解析；原始 PDF 等內容仍由 Engine 的相容 Parser 處理。
- Payload 採扁平格式，不需要 source 或 mode；content／base64／uri 三選一。
- **API 單筆文件與 Parser Input 共用 IngestionDocument 及同一份 JSON Schema**；Parser 可接收經共同驗證／反序列化的 SDK 物件，但欄位、型別與驗證規則一致，不維護第二份轉換後的輸入 contract。
- 接受未解析內容與上游已解析內容；後者由相容 Parser／Adapter 驗證及正規化，不強制重做解析。這不等於已核可直接匯入 Chunk／vectors。
- Parsing 可啟用多個 Parser，平台依能力自動路由；格式不重疊時不要求使用者配置 Router。同格式衝突才需預設策略或進階 parsing_profile。
- 沒有相容 Parser、路由歧義、格式與實際內容不符時明確報錯，不以載入順序選第一個，不默默改用其他 Parser。

<a id="src-13-2-單筆文件-json-schema"></a>
## 單筆文件 JSON Schema

機器可讀共同定義：[ingestion_document.schema.json](../schemas/ingestion_document.schema.json)。它是 API 與 Parser Input 的同一份外層 Schema；單位是單筆文件，不是整個批次或 HTTP 回應。最小 List item／Parser Input 為（完整 HTTP body 需包成 [此物件]）：

唯一機器 Schema：[ingestion_document.schema.json](../schemas/ingestion_document.schema.json)。

固定外層與互斥條件以此檔為準；以下保留正規化與內容驗證邊界。

| 欄位 | 型別 | 必填與語意 |
|---|---|---|
| document_id | 非空 string | 必填，穩定文件識別；一來源產生多文件時的 ID 派生另議 |
| content | 非空 string 或非空 object | 與 base64／uri 三選一；物件內部由 Parser 的 input schema 驗證 |
| base64 | 非空 string | 與 content／uri 三選一；標準 Base64，不含 data URI 前綴 |
| uri | URI string | 與 content／base64 三選一；Engine 必須有存取能力及授權 |
| media_type | 非空 string | MIME type；僅在可由 Config 或可靠資訊唯一決定時可省略 |
| schema_id | 非空 string | 必要時區分不同 JSON 內容結構及版本，不是任意可下載／執行的 Schema URL |
| parsing_profile | 非空 string | 選用此 System 已設定的解析策略；不是 Python import path 或任意 component_id |
| source_revision | 非空 string | 可省略，省略後的版本生成政策待 Q-007／Q-008／Q-015 核定 |
| metadata | object | 可省略；平台補 {}，並依 System metadata schema 驗證 |

共同外層 additionalProperties=false；content／metadata 的業務內容由各自契約繼續驗證。所有已宣告欄位都不接受 null。content 暫不接受根層 array／number／boolean；若 Parser 需要清單，可在其明確宣告的物件欄位中承載，未新增通用陣列模式。minLength 不代表 trim／全空白政策已定案。

JSON Schema 中沒有 default 副作用；metadata={} 是平台正規化行為。contentEncoding／format 不能取代實際 Base64 解碼、URI 協定及存取檢查。共同 Schema 通過，只代表外層合法，不代表內容可被 Parser 處理。

D-67：Parser 的 Descriptor／Manifest 宣告共用 Input／Output 引用與固定或依 Config 細化的資料規格，見 [Descriptor](04_component_descriptor.md)。API 仍直接交相同 IngestionDocument，不新增 ParserInput。接收時可判定的路由／內容欄位可加入 202 前整批快速預檢；需下載、解碼、辨識或解析才可確認的檢查仍在背景工作，202 不表示解析成功。輸出驗 ParsedDocument 共用 Contract＋當前資料細節；不要求 User 再填一份全域 document_schema。


D-58 已確認一支 POST /v1/ingestions，body 為非空 IngestionDocument[]，單筆亦一元素 List；整批預檢通過才 202，執行逐文件結果、Run 可 partial。每筆使用本共用 Schema；完整回應／錯誤 OpenAPI 仍待整理，見 Runtime API／部署手冊。

<a id="src-13-3-輸入範例"></a>
## 輸入範例

<a id="src-13-31-結構化-json"></a>
### 結構化 JSON

```json
{
  "document_id": "product-001",
  "content": {
    "title": "操作手冊",
    "text": "產品使用說明",
    "summary": "快速操作摘要"
  },
  "metadata": {"department": "engineering"}
}
```

預設 Structured JSON Parser 可依既定設定把 content 的鍵轉為 ParsedDocument.units 中每筆 dict 的直接欄位；正式預設／必要欄位與未知欄位政策仍由 Q-002 決定。Builder CSV 映射只做一次；若已映射成目標鍵，Parser 不重複映射。metadata 使用外層欄位，不從任意 content 欄位自動猜測。

<a id="src-13-32-pdf-資源引用"></a>
### PDF 資源引用

```json
{
  "document_id": "report-001",
  "uri": "https://storage.example.com/report.pdf",
  "media_type": "application/pdf"
}
```

<a id="src-13-33-pdf-base64"></a>
### PDF Base64

```json
{
  "document_id": "report-002",
  "base64": "JVBERi0xLjcKJSVFT0YK",
  "media_type": "application/pdf"
}
```

此字串是可解碼的示意內容，不是有效 PDF 測資；必須再由 Parser 驗證檔案。Base64 約增加 1/3 傳輸體積；實際 body、解碼後檔案、下載大小及逾時上限尚未核定，不把先前提議的 5 MB 當產品限制。

<a id="src-13-34-上游已解析資料"></a>
### 上游已解析資料

content 可由已註冊 Adapter 接收 {"units": [...]}，驗證後搭配外層 document_id、source_revision、metadata 形成 ParsedDocument。此為已解析內容的示意 Profile，正式 schema_id 名稱仍待核定；不是直接接受 Chunk 或向量。原生供應者結構也可放 content object，但須由相容 Parser 展平為 Units。ID／metadata 重複來源需明定一致性政策，不得靜默覆寫。

<a id="src-13-4-是否也是-parser-的-input"></a>
## 是否也是 Parser 的 Input？

**是，Ingestion API 每個 List item 與 Parser Input 共用 IngestionDocument 及相同 Schema；完整 HTTP body 是文件 List，Parser 接收其中一份文件。** 內容解碼由共用 resolver 處理，不建立另一份公開輸入契約。

<a id="src-13-41-共用物件透過-sdk-取得內容"></a>
### 共用物件，透過 SDK 取得內容

| API／Parser 共用欄位 | SDK 共用內容取得能力 | Parser 取得後處理的值 |
|---|---|---|
| content 是文字 | 直接使用 | str |
| content 是 JSON object | 保留物件，驗證相容 schema | dict |
| base64 | 檢查大小、嚴格解碼 | bytes／核可的可讀取資源 |
| uri | 授權取得、檢查限制並依格式處理 | 文字、JSON 或二進位資源 |

這裡取得的值是 Parser 執行中使用的內容，不是第二份 Parser Input schema。共用文件仍保留原本 content／base64／uri 三選一；不得把解碼後 bytes 塞入共用 JSON content，也不因 resolve 而另加 content，使輸入同時存在兩種來源。API 的 JSON 與 SDK 物件可以有序列化層面的表示差異，不能改變共同契約的語意。

JSON API 不直接傳 bytes；PDF／PPTX／Excel 等檔案使用 Base64 或 URI。media_type 表示內容格式，不能取代來源欄位判定；即使只有一個 Parser，仍需區分 literal 文字、編碼內容與資源引用。media_type／schema_id 可在 Config 或可靠資訊足以唯一判定時省略，不能用 Parser 數量作為唯一判準。

SDK 提供共用的 resolver，Parser Developer 不自行重做 URL 下載、Base64 解碼與資源限制。下面只有介面示意，並不是已發布的 SDK，實際型別、函式命名與同步／非同步簽名仍待 Q-002／Q-017：

```python
async def parse(self, document: IngestionDocument, context):
    content = await context.content_resolver.resolve(document)
    # 依此 Component 的能力解析 content，保留文件身分及 metadata，
    # 再產生符合 ParsedDocument contract 的結果。
    ...
```

路由依共同文件及已設定能力選出相容 Parser；parsing_profile 選已核可實例，不要求 Parser 再做一次路由。取得、格式偵測及預檢的精確時點待定，可由平台預先取得或共用 resolver 處理；不得因共用 Schema 就跳過實際格式與 Parser 內容驗證。

<a id="src-13-42-context-不屬於-api-payload"></a>
### context 不屬於 API payload

context 是 Engine 建立的執行資源，由 Engine 傳給 Parser；呼叫端不用在 JSON 裡提供。以下為責任規劃，不表示公開 class 的屬性已凍結：

| 執行資源 | 用途 |
|---|---|
| 共用內容 resolver | URI 取得、Base64 解碼與資源限制 |
| request／run 追蹤 | 模組 Log、診斷與來源追溯 |
| 執行控制 | 必要時提供取消／逾時與資源釋放 |

Component 參數與服務設定可在建立 Instance 時注入，不必全部塞進 context。可信來源資訊、授權與 Secret 由平台資源／受控 Context 處理；不新增 API 的 source_info 欄位，不信任 metadata 覆寫可信資訊。

document_id、source_revision 及有效 metadata 持續傳遞；省略版本的生成政策仍待定。resolver 的 bytes／stream／resource handle、快取／重用、生命週期與 Context 精確介面待 Q-002／Q-016／Q-017，但「共用輸入 Schema」不再列為待決。

<a id="src-13-5-parser-能力與-chunker-相容"></a>
## Parser 能力與 Chunker 相容

Parser 宣告可接受的 media_type、schema 及必要資源；多個 Parser 的啟用不代表每筆都執行全部，也不保證混合模態的聯合理解。相同格式只有一個可用實例時自動選用；有重疊時需明確預設／profile。格式副檔名僅為提示，不取代實際驗證。

ParsedDocument 使用唯一的平面 units 格式；Chunker 檢查指定字串欄位、Markdown 格式與 Tokenizer 能力，不再依 text-spans／page-blocks 配對或路由。Parser 負責將結構整理成可獨立切分的 Units；不支援的來源由 Parser 明確拒絕。詳見 資料契約。

<a id="src-13-6-驗證邊界與待決事項"></a>
## 驗證邊界與待決事項

- API／Parser 先驗同一份 IngestionDocument 外層，再驗相容 Component 的 content／實際格式限制；支援 JSON object 不代表可匯入任意內容、Chunk 或向量。
- Parser 輸出依 資料契約 的四鍵 Units Schema 與語意驗證；Chunker 輸出依 資料契約 的六鍵 Schema、來源／任務／向量規則。資料形狀符合仍須檢查 Component 能力相容。
- Builder 將文件／CSV 轉成共同 JSON；是否提供暫存 URI、格式轉換範圍、存取與清理見 Q-016／Q-019。
- 剩餘待決：schema_id／profile 命名與版本、路由衝突的精確政策、輸入／解碼／下載大小與逾時、批次 envelope、回應／錯誤碼、ID／版本省略政策及正式 SDK。已確認的共同外層不重開。
- UI 遷移記 [UIB-011](07_builder_ui.md#uib-011-ingestion-parser-routing)；ParsedDocument／Chunk 預覽另見 UIB-012／013，本次不修改 Prototype。

<a id="src-14-0-情境與分類結果報告摘要"></a>
## ParsedDocument：情境與分類結果（報告摘要）

所有 Parser 都產出同一種 ParsedDocument；不同來源只影響 Parser 的整理策略，不增加 Chunker 輸入結構種類。

| 來源情境 | Parser 整理方式 | Chunker 接到的內容 |
|---|---|---|
| 純文字／多欄位 JSON／CSV 列 | 文字或紀錄整理成一個 Unit | 一筆 dict，預設 text，其他為可複製欄位 |
| PDF／PPT／Excel、已有 page／span／block | Parser 決定閱讀順序、段落／章節／頁面邊界，展平成 Units | 有序的獨立 Unit；page／slide／sheet 是來源欄位，不是結構路由 |
| 表格 | 逐列補上表頭語意，或整表轉 Markdown | 每列一個 Unit，或整表一個 Unit |
| 圖片／流程圖 | 具備能力的 Parser 產生 OCR／描述，可附來源 URI | 描述放 text；Chunker 不解讀圖片 |
| 上游已解析資料 | Adapter 驗證／正規化成 Units | 與原始資料解析後完全相同的契約 |

<a id="src-14-01-分類範例"></a>
### 分類範例

<a id="src-14-011-純文字紀錄一個-unit"></a>
<a id="src-14-012-多頁章節獨立-units保留-markdown-標題"></a>
<a id="src-14-013-表格逐列補齊語意"></a>
<a id="src-14-014-圖片描述文字與來源-uri"></a>
<a id="src-14-015-既有-docling-官方文字摘錄重新包裝成一個-unit"></a>
<!-- classification-examples:parsed:start -->

所有例子共用四個頂層鍵；分類代表來源情境，不是不同結構型別。

#### 純文字／紀錄：一個 Unit

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "units": [{"text": "清潔前先斷電。", "title": "設備手冊"}],
  "metadata": {"filename": "manual.pdf"}
}
```

#### 多頁／章節：獨立 Units，保留 Markdown 標題

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "units": [
    {"text": "## 帳號申請\n填寫申請單，送交主管核准。", "section_title": "帳號申請", "page": 1},
    {"text": "## 密碼重設\n使用公司信箱申請重設密碼。", "section_title": "密碼重設", "page": 2}
  ],
  "metadata": {"filename": "manual.pdf"}
}
```

#### 表格：逐列補齊語意

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "warranty",
  "source_revision": "v1",
  "units": [{"text": "產品 A 的保固為 1 年。", "product": "A"}, {"text": "產品 B 的保固為 2 年。", "product": "B"}],
  "metadata": {"filename": "manual.pdf"}
}
```

#### 圖片：描述文字與來源 URI

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "flow",
  "source_revision": "v1",
  "units": [{"text": "員工提出申請 → 主管審核 → IT 建立帳號。", "image_uri": "https://example.com/flow.png", "page": 3}],
  "metadata": {"filename": "manual.pdf"}
}
```

#### 既有 Docling 官方文字摘錄：重新包裝成一個 Unit

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "docling-multi_page",
  "source_revision": "e90f3440e9091b51a9c7fb0b138003933d71f540f24f4d04c05aa58fe3eb747a",
  "metadata": {
    "_rag": {
      "provider": "docling",
      "preview": true,
      "note": "Historical verified excerpt repackaged as one unit; provider not rerun for 0.2."
    }
  },
  "units": [
    {
      "text": "The Evolution of the Word Processor\n\nThe concept of the word processor predates modern computers and has evolved through several technological milestones.",
      "page": 1
    }
  ]
}
```

<!-- classification-examples:parsed:end -->

<a id="src-14-1-唯一共用-schema"></a>
## ParsedDocument：唯一共用 Schema

[JSON Schema](../schemas/parsed_document.schema.json) 是形狀來源；[validate.py](../examples/parsed_document/validate.py) 檢查補充語意。

| 頂層欄位 | 型別 | 規則 |
|---|---|---|
| document_id | string | 必填非空文件識別 |
| source_revision | string | 必填非空來源版本；自動產生政策仍由 Q-007 定案 |
| units | list[dict] | 必填非空、有序列表；每筆直接放欄位，不包 fields、不要求 unit_id |
| metadata | object | 必填，可為 {}；文件層資訊，Chunk 預設完整繼承 |

頂層禁止未知鍵；移除 fields 與 structure。Unit 是欄位集合，沒有 children、parent 或遞迴 Unit 協定。內容欄位沿用 JSON 值能力，允許複製業務資料；物件型欄位不會被通用 Chunker 當成另一棵文件結構遍歷。Parser 若有需要可自行提供 unit_id，平台不強制、不依賴它。

預設每筆提供字串 text。共用 Schema 不強制 text，以保留進階自訂切分欄位；選定的 split_field 必須在每個 Unit 存在且為非空白字串，copy 欄位亦須存在。異質 Units 不能靠靜默略過缺欄位；Parser 應先正規化成所選任務可處理的欄位集合。空文件／空白頁處理由 Parser 政策明示，不能把空白 Unit 當作成功可搜尋內容；空白頁來源可記 metadata。

<a id="src-14-2-parser-與-chunker-分工"></a>
## ParsedDocument：Parser 與 Chunker 分工

| 責任 | Parser | Chunker |
|---|---|---|
| 文件解碼、OCR、閱讀順序、表格／圖片轉文字 | 負責 | 不負責 |
| 決定每個獨立內容單位的邊界與上下文 | 負責，可把跨頁內容整理為同一 Unit | 尊重 Unit 邊界 |
| text-spans／page-blocks 等供應者表示 | Parser／Adapter 內部處理並展平 | 不接收這些結構規格 |
| 單筆文字內 Fixed-size／Recursive／Header-aware 切分 | 不要求實作 | 負責 |
| copy、metadata 繼承、來源範圍、Chunk ID | 提供來源內容 | 負責 |

**不跨 Unit 合併、不跨 Unit overlap。** 第一筆切 2 個、第二筆切 3 個，輸出共 5 個。小 Unit 可能產生較短 Chunk，若要合併段落，Parser 先整理成同一 Unit。每個任務選一個 Chunker；移除依 structure.schema_id 選 Chunker 的 Router，Parser 依輸入格式派送仍保留。

Header-aware 讀取 Unit 中的 Markdown #／##，不要求 heading Block。Parser 要保留標題與其內文於同一 Unit，或把上下文複製到各 Unit。標題與內文分成不同 Units 後，Chunker 不跨筆恢復關係。超長章節可再用 Recursive；其參數及無標題時的明確策略由 Component 宣告，不能無聲換方法。

<a id="src-14-21-metadata-的描述與處理提示d-52"></a>
### metadata 的描述與處理提示（D-52）

ParsedDocument.metadata 可攜帶合法附帶資訊，或由下游 Component 明確支援的文件層提示，例如 chunking_mode=passthrough；Parser 依自身規則保存／產生，Chunker 按約定讀取。Unit 仍是平面內容物件，不新增根層 processing／options。metadata 的型別與允許鍵仍受共用 Contract 及適用 Component 的資料規格／參數驗證；D-67 不再要求頂層 document_schema，細節見 [Descriptor](04_component_descriptor.md)；模型、連線及 Secret 不因而搬進 metadata。詳細缺省與 passthrough 語意見 [Chunk](#src-15-1-共用物件)。

<a id="src-14-3-來源追溯與欄位傳遞"></a>
## ParsedDocument：來源追溯與欄位傳遞

Chunk.fields 保持單一 dict：`ParsedDocument.units[i][split_field] → Chunk.fields[output_field]`。選定 copy 欄位取自同一 Unit，完整原文需要時明確映射 original_text，不能覆蓋切片。

Component 選擇提供 Chunk.metadata._rag.source_refs 時，使用 unit_index（0-based）、field、output_field、role 及文字 start／end。位置以該版本 Unit 的來源字串為基準，Unicode code point、半開範圍 [start,end)，不是整份文件 offset，也不是 Token／UTF-16／PDF glyph offset。unit_index 可由 Component／SDK helper 記錄，不要求 Parser 提供，也不要求所有 Chunker 輸出來源引用。

page、slide、sheet、section_title、image_uri 等自訂來源欄位不會因存在就自動複製；要供下游使用需納入 copy。文件 metadata 仍全繼承；可信 metadata 保留區政策見 Q-006。原生解析樹不再是共用契約，必要時由 Parser 保存於追溯 metadata／外部 artifact，不讓 Chunker 重新解讀。

<a id="src-14-4-取捨與驗收"></a>
## ParsedDocument：取捨與驗收

- 共用 Schema 統一後，仍須檢查所選欄位型別、文字格式、Tokenizer 與模型上限。
- 表格整體轉 Markdown 後，按長度切分可能破壞列或丟掉表頭；Parser 可採逐列文字以避免。特殊保護策略尚未因此核定或實作。
- 圖片沒有 OCR／描述時，不應填空 text 並宣稱可檢索；缺資源及不支援格式需明確回報。
- Header-aware、Recursive、Fixed-size 都只在 Unit 內運作；實際 Tokenizer／演算法實作驗收與資料形狀測試分開。
- 測試需包含多 Unit、特殊字元、缺欄位、空內容、copy 衝突及不跨 Unit；ordinal／來源還原只驗收有宣告提供的追溯能力，不因缺少 _rag 拒收。

<a id="src-14-5-parser-相容性與驗證範圍"></a>
## ParsedDocument：Parser 相容性與驗證範圍

| 候選 Parser | 新契約的映射方向 | 本次狀態 |
|---|---|---|
| Docling | 依閱讀順序將文字／表格等整理成 Units；必要的標題上下文由 Adapter 附帶 | 已將既有官方文字摘錄重新包裝並驗證；未重跑完整 provider 測資 |
| MinerU | 將頁面／元素結果整理成 Units，保留需要的來源欄位 | 映射方向可行；新版完整 Adapter 與測試待開發 |
| MarkItDown | Markdown 整份一個 Unit，或 Parser 先整理成數個 Units | 不再需要產生 text-spans；新版實際解析整合待驗證 |
| PyMuPDF4LLM | Markdown 一個 Unit，或逐頁文字各成 Unit；Layout 資訊在 Parser 內處理 | 新版空白頁／跨頁／表格策略與整合待驗證 |

這是來源表示的設計對照，不是供應者直接輸出本 Schema 的承諾。0.1 的舊規格／官方測資對照已歸檔至 [歷史 ParsedDocument 0.1](history/superseded/parsed_document_0.1.md)，供查驗、不作新版驗收證據；[固定測資清單](../examples/parsed_document/provider_cases.json) 仍供後續重驗。

本次本地驗證是 [test_contract.py](../examples/parsed_document/test_contract.py) 的新正負案例及 [Docling 摘錄](../examples/parsed_document/docling_report_excerpt.json)，未執行外部模型或重新量測解析品質。

<a id="src-15-0-情境與結果摘要"></a>
## Chunk：情境與結果摘要

| 情境 | 行為 |
|---|---|
| 預設 | 每個 Unit 的 text 獨立切分，輸出 Chunk.fields.text；copy_fields=[] |
| 多 Unit | 各筆結果串接，2＋3＝5；不合併、不跨 Unit overlap |
| 多欄位任務 | 每個任務遍歷 Units，結果相加，不做笛卡兒積 |
| 保留原文／上下文 | copy 同一 Unit 的欄位；原文另名 original_text，不能覆蓋切片 |
| 來源位置（選用） | Component 可提供 metadata._rag.source_refs：unit_index＋field＋start/end；未提供不報錯、不捏造 |
| Embedding／Indexing | 沿用命名向量物件與完整保存規則 |

<a id="src-15-02-使用同一份-schema-的資料例子"></a>
<!-- chunk-report-examples:start -->

### 使用同一份 Schema 的資料例子

以下由共用 cases.json 產生，包含完整預設 Chunk、進階多欄位結果及來源／向量片段。Hash 是參考規則的實際結果；完整來源與設定見同一案例檔。

**預設：只切 text，不複製其他 fields**

```json
{
  "chunk_id": "chk_25f40b1f36ef7154df4806eb5fe1317db1836f46e0705749efd676b44cbe9182",
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {
    "text": "清潔前先斷電。"
  },
  "metadata": {
    "department": "engineering",
    "_rag": {
      "source_refs": [
        {
          "unit_index": 0,
          "field": "text",
          "output_field": "text",
          "role": "split",
          "start": 5,
          "end": 12
        }
      ],
      "chunking": {
        "chunking_fingerprint": "40da9219f54a8d552281e6fa3573e98352e450df39d8ac6e6c3ed287877a31a3",
        "chunk_ordinal": 0,
        "task_id": "text"
      }
    }
  },
  "vectors": {}
}
```

**進階：T 切 2 段、F 切 3 段，各自預設輸出 text；完整來源明確複製到不同名稱**

| ordinal | task_id | fields.text（片段） | fields.original_faq（完整） | fields.original_text（完整） |
|---|---|---|---|---|
| 0 | text | 甲段。 | 問一。問二。問三。 | — |
| 1 | text | 乙段。 | 問一。問二。問三。 | — |
| 2 | faq | 問一。 | — | 甲段。乙段。 |
| 3 | faq | 問二。 | — | 甲段。乙段。 |
| 4 | faq | 問三。 | — | 甲段。乙段。 |

**兩個獨立 Units：第一筆切 2 段、第二筆切 3 段，共 5 個 Chunk，不跨筆合併**

```json
[
  {
    "text": "甲段。",
    "source_refs": [
      {
        "unit_index": 0,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 0,
        "end": 3
      },
      {
        "unit_index": 0,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "乙段。",
    "source_refs": [
      {
        "unit_index": 0,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 3,
        "end": 6
      },
      {
        "unit_index": 0,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "問一。",
    "source_refs": [
      {
        "unit_index": 1,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 0,
        "end": 3
      },
      {
        "unit_index": 1,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "問二。",
    "source_refs": [
      {
        "unit_index": 1,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 3,
        "end": 6
      },
      {
        "unit_index": 1,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  },
  {
    "text": "問三。",
    "source_refs": [
      {
        "unit_index": 1,
        "field": "text",
        "output_field": "text",
        "role": "split",
        "start": 6,
        "end": 9
      },
      {
        "unit_index": 1,
        "field": "page",
        "output_field": "page",
        "role": "copy"
      }
    ]
  }
]
```

**Embedding 後：vectors.text 的內容**

以下向量為契約用示意數值，沒有呼叫模型；Profile 與來源欄位必須符合可信 Binding。

```json
{
  "values": [
    0.12,
    -0.08,
    0.31
  ],
  "embedding_profile_id": "embedding-demo-v1",
  "source_field": "text"
}
```

<!-- chunk-report-examples:end -->

<a id="src-15-1-共用物件"></a>
## Chunk：共用物件

[Schema](../schemas/chunk.schema.json)、[案例](../examples/chunk/cases.json)、[參考驗證](../examples/chunk/contract.py) 共用同一契約。參考工具只組裝已給定切片，不是 Fixed-size／Recursive／Header-aware 的正式實作。

| 必要頂層欄位 | 內容 |
|---|---|
| chunk_id | 非空字串；參考產生規則見 [Chunk相關章節](#src-15-6-chunk-id序號與重建) |
| document_id／source_revision | 繼承 ParsedDocument |
| fields | 單一非空 dict；切分片段與明確複製欄位 |
| metadata | 繼承合法文件 metadata，可為 {}；Component 可選擇提供 _rag.source_refs／chunking |
| vectors | Chunker 輸出 {}；Embedding 後為命名向量物件 |

正式 Chunker 輸出也不強制提供 _rag、source_refs、fingerprint 或 ordinal；由 Component 決定是否實作。提供標準追溯欄位時才檢查其格式及可取得的來源一致性，未提供不報錯。六個根鍵與文件識別、欄位／向量等既有規則維持。檢索可省略向量令 vectors={}，不表示刪除已儲存向量。

<a id="src-15-2-切分與欄位映射"></a>
## Chunk：切分與欄位映射

- 預設 split_field=text、output_field=text、copy_fields=[]；來源是 units[i][split_field]，不是 ParsedDocument.fields。
- 每筆 Unit 獨立；每個任務選一個 Component。Fixed-size 依 Token 視窗，Recursive 依分隔符／Token 上限，Header-aware 依 Unit 內 Markdown 標題，超長章節可再 Recursive。
- 所有必要任務套用所有 Units。缺 split 欄位、非字串、全空白、缺明確 copy 欄位、必要 task/unit 零產出都報錯。第一版不新增逐 Unit 路由或可選複製開關。
- 同欄位可切分又完整複製，但目的名稱須不同；進階多任務預設都輸出 text。copy 只讀同一 Unit，不取其他 Unit 補欄位。
- Markdown 標題與內文若被 Parser 分開為不同 Units，Chunker 不跨筆重組。Parser 決定語意單位；Chunker 決定筆內切片。
- 所有輸出欄位名在任務內唯一；copy 欄位可能很長，仍需檢查後續模型輸入上限。

<a id="src-15-3-來源追溯component-選用"></a>
## Chunk：來源追溯（Component 選用）

本節只規範「有提供」的標準欄位；不要求所有 Component 產生。SDK 可提供組裝／驗證工具，有需要才使用，不強制逐一重寫追溯邏輯。沒有追溯時仍可依 document_id／chunk_id 使用資料，但不保證頁內定位、切片還原或完整來源診斷。

| SourceRef 欄位 | 規則 |
|---|---|
| unit_index | 必填整數，0-based；對應本版 ParsedDocument.units 的位置 |
| field／output_field | 必填；來源 Unit key／目的 Chunk.fields key |
| role | split 或 copy |
| start／end | 成對選填；來源 Unit 字串的 Unicode code point 半開範圍 [start,end) |
| chunk_start／chunk_end | 成對選填；輸出字串的本地範圍，用於同一 Unit 的多段來源 |

範例來源：`units[1]["text"][0:3]` 對應 `{unit_index: 1, field: "text", output_field: "text", role: "split", start: 0, end: 3}`。範例使用 Python 位置語意，不能拿 Token 或 UTF-16 offset 直接代入。

同一 Chunk 的來源引用必須指向同一 Unit。copy 表示完整值，不帶文字範圍。移除 schema_id／block_id／block_start／block_end／結構 Location 引用；page 等來源欄位由 Parser 提供並依 copy 設定帶入 fields，不再要求 Chunker 解讀 Block。

若宣告提供精確切片追溯，來源字串與切片需可還原。Header-aware 去除標題／重組文字時，可以不提供追溯；若提供，須使用正確來源／輸出範圍及對應語意驗證，不能捏造連續範圍。這不是新增任意 concat 功能。

<a id="src-15-4-metadata向量與下游"></a>
## Chunk：metadata、向量與下游

文件 metadata 全繼承，平台可信欄位仍由 Engine 控制，不能用業務 metadata 覆寫授權。_rag 選填；unit_index／範圍／fingerprint 有需要時由 Component 或 SDK 輔助產生，不列一般 UI 必填設定。Unit 內可選 unit_id 只是 Parser 欄位，通用 Chunker 不依賴它。

<a id="src-15-41-metadata-可以攜帶-component-的處理提示"></a>
### metadata 可以攜帶 Component 的處理提示

metadata 可同時保存描述資訊與 Component 解讀的處理提示，例如：

```python
metadata = {
    "department": "製造部",          # 描述／搜尋過濾
    "chunking_mode": "passthrough", # 本例 Chunker 的文件層處理提示
}
```

chunking_mode 是示範 Component 約定，不是所有 Component 必須認識的全域保留 key。Developer 說明會讀取哪些 key、型別、允許值、未提供時的預設及不支援值的處理；使用者資料也須通過共用 Contract 及適用 Component 的 metadata 資料規格／設定（若採拒絕未知欄位，需宣告此 string 欄位）；D-67 不再要求獨立頂層 document_schema，見 [Descriptor](04_component_descriptor.md)。Parser 保留／產生合法提示，Chunker 讀取它，不新增三份共用物件的根欄位。

支援本約定的 Chunker 可直接 `document.metadata.get("chunking_mode", "split")`：缺省正常切分；passthrough 時每 Unit／文字任務完整轉成一筆 Chunk，仍建立 chunk_id、依設定 copy 欄位、繼承 metadata、初始化 vectors={}。不跨 Unit 合併，三個 Units 的單一任務得到三筆，不是整份文件一筆；有多任務仍依任務規則串接。提示不支援時依該 Component 的已宣告行為處理，不能讓平台憑空保證所有 Chunker 都會遵守。

第一版不另建通用條件規則引擎，也不要求 UI 多填一份判斷式；這不是 Config 的任意覆寫入口。固定模型／演算法參數、連線、Secret 仍放 Config／環境綁定，不藏進 metadata。passthrough 不跳過文字／欄位、必要產出及 Embedding 長度檢查；超長仍報錯，不默默截斷。文件提示改變切分結果時需重新 Ingestion，ID／更新處理由選用 Component 的既定策略處理，不要求為此輸出 fingerprint。


<a id="src-15-42-向量與下游"></a>
### 向量與下游

vectors[name] 仍為 `{values: [...], embedding_profile_id: "...", source_field: "text"}`，有限數值、維度／Profile／來源需符合 Binding。Indexing 預設保留完整 fields／metadata／vectors；Rerank／檢索結果消費端 所需內容在 Chunk 自備，不強制回查 ParsedDocument。

<a id="src-15-5-有效切分設定與-fingerprint選用參考工具"></a>
## Chunk：有效切分設定與 fingerprint（選用參考工具）

以下是平台提供的參考 helper 規劃及完整追溯範例所採做法，不是每個 Component 的必要實作；不使用本演算法或不輸出 fingerprint 仍可符合共用 Chunk Contract。

chunking_spec 是 Engine 解析後的**有效切分執行設定**，不是每個 Chunker class 的固定值，也不是多一份由使用者手填的資料。參考格式名稱為 chunking-spec/0.1-draft；完整 Pipeline Config 的 Schema 仍由 Q-002／Q-004／Q-025 核定。

| 內容 | 納入 fingerprint 的原因 |
|---|---|
| 有序 tasks、唯一 task_id | 決定多欄位輸出順序與任務識別 |
| Component ID／實作版本 | 演算法版本可能影響邊界或結果 |
| split／output／copy 映射 | 決定輸出內容與欄位 |
| 解析後有效參數／Tokenizer ID 與 revision | size／overlap／分隔符／正規化等會影響結果 |

未啟用的方法參數、UI 收合狀態、HTTP 連線、Secret、Run ID、Embedding／Retrieval／Rerank 設定不納入。預設值須先補齊；每個任務記錄選用的 Component／版本與有效設定。本文範例 tokenizer 是示意識別，沒有下載或驗證真實 Tokenizer。

同一份解析後設定處理不同文件，fingerprint 相同；同一個 Recursive Component 改欄位、長度或版本，fingerprint 不同。本參考工具採**整份有效任務計畫的一個 fingerprint**；改其中一個任務會影響這份文件所有 Chunk ID，換取簡單一致的重建語意，暫不承諾逐任務局部保留 ID。

參考計算：json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) → UTF-8 → SHA-256。保留字串原樣，不偷偷做 Unicode normalization。這是 Python 草案規範；跨語言的數字正規化與正式 canonicalization 仍在 Q-007，不能用 Python 內建 hash()。

<a id="src-15-6-chunk-id序號與重建"></a>
## Chunk：Chunk ID、序號與重建

chunk_id 仍為必要非空識別，輸出清單內不可重複。可由 Component 或 SDK helper 產生，不強制它必須由 fingerprint／ordinal 計算；穩定性、冪等與更新範圍須依選用實作及 Q-007／Q-008 說明。以下 fingerprint／ordinal／SHA-256 規則只適用採用本參考工具的 Component，不是缺少 _rag 就拒收的理由。

若選擇提供 metadata._rag.chunking，記錄 chunking_fingerprint、chunk_ordinal、task_id，三者遵守該標準區塊格式。實際 spec 存在可追溯 Config／Run，不在每個 Chunk 重複。

- chunk_ordinal 是同一文件本次輸出的**全域** 0-based 序號，依設定任務順序，再依 unit_index，最後依 Unit 內穩定切片順序編排；不是每個欄位各從 0 開始。
- 任務併行時先按上述順序整併，再產生 ID；不能使用完成先後順序。相同輸入的 Component 若不具決定性，須明確宣告並提供可重現策略，不能承諾穩定 ID。
- 參考 chunk_id 為 chk_ 加上 SHA-256；輸入是 document_id、source_revision、chunking_fingerprint、chunk_ordinal 的固定 JSON。完整可執行函式在 contract.py。
- 文件內容變更更新 source_revision；切分設定變更更新 fingerprint；只換 Embedding 或 Inference 設定不改 Chunk ID。相同 revision 不得偷偷表示不同來源內容；來源版本產生與衝突政策仍由 Q-007／Q-008 定案。
- 文件／Chunk ID 作用域為 System；存取必須另帶可信 System 範圍，相同字串不授權跨 System 存取。

重建應先準備新一批完整資料，成功後切換；失敗保留原本可用資料，不搜尋新舊混合版本。這是本輪同意的行為方向；ES／Local Search 的發布、併行更新、部分失敗、舊資料清除與可查詢時點仍在 Q-008～Q-010／Q-015，未實作原子交易。Memory 重啟仍依既有規則重新 Ingestion，不因 fingerprint 就可恢復資料。

<a id="src-15-9-後續確認與欄位組裝d-532026-11-03-已確認功能方向"></a>
## Chunk：後續確認與欄位組裝（D-53，2026-11-03 已確認功能方向）

- D-48 已確認：多任務預設將切分片段寫 fields.text；完整原文複製採不衝突名稱，進階仍可自訂。第一版必要切分欄位缺失／型別錯誤／全空白、明確 copy 欄位缺失或必要任務零產出均明確失敗；可選複製不先擴充。
- Parser 改變需重新處理受影響文件：Parsing → Chunking → Embedding（有配置時）→ Indexing；原始資料可取得時不代表一定要重新上傳。多 Parser 路由的重跑範圍、原始資料保留、重新發布仍須依有效相依與儲存政策決定。這是執行影響說明，沒有新增已實作的重跑／快取能力。
- 重新 Ingestion 與 ID 是否納入解析後輸入內容摘要是不同問題；目前 Hash 規則尚未修改。原始文件版本不變但 Parser 輸出改變時的 ID／index_generation 識別仍在 Q-007／Q-015。
- D-53 已確認：預設 Embedding Component 提供選用模板組合；預設 Chunker 提供選用原文 Chunk。v0.12 已加入 UI 設定／字串預覽及字元教學案例；Engine 與三份 Ingestion 資料 Schema 維持原狀；不是所有自訂 Component 的必要能力。

<a id="embedding-field-composition"></a>
<a id="src-15-91-embedding-前的欄位模板組合"></a>
### Embedding 前的欄位模板組合

- 位置：Chunking 後、Embedding 呼叫前，由預設 Embedding Component 前處理，不新增 Pipeline Module。
- UI：提供預設關閉／收合的「內容組合」，啟用後填模板與輸出欄位名稱；預設輸出 fields.embedding_text，既有 Embedding 來源／向量名稱映射仍可設定。
- 支援欄位替換與固定文字，不執行 Python／任意程式，也不呼叫 LLM。第一版以明確的 fields.* 文字欄位為主；缺欄位、型別不符、語法錯誤或輸出命名衝突要報錯，不默默換值或覆寫原 text。
- 先寫入衍生欄位，再走原有映射與模型輸入檢查；新欄位隨 Chunk 一起保存，讓使用者可檢查實際組合的內容。

範例模板（語意已確認；正式設定 Schema／解析器細節待核定）：

```text
標題：{{fields.title}}
內容：{{fields.text}}
```

套用後的 fields：

```python
fields = {
    "title": "設備保養",
    "text": "清潔前先斷電。",
    "embedding_text": "標題：設備保養\n內容：清潔前先斷電。",
}
```

映射可設為 fields.embedding_text → vectors.text；向量 source_field 記 embedding_text，向量名稱不必同名。模型 Profile／document encoding prefix 的規則維持，不能將同一前綴重複加兩次；本模板只用於文件 Chunk，不隱含套用到 Query Encoding。

對最終模型輸入檢查 Token 上限，包含組合內容、Profile 前綴與特殊 Token。模板／輸出欄位／映射等有效變更屬 Ingestion 邏輯變更，需重新組合、Embedding 與 Indexing；是否可重用既有 Chunk 依來源保留能力與 Q-015，不承諾自動局部重跑。一般自訂 Component 只有明確宣告支援時才提供此功能。

<a id="include-original-chunk"></a>
<a id="src-15-92-chunker-額外保留完整原文-chunk"></a>
### Chunker 額外保留完整原文 Chunk

| 選項 | 行為 |
|---|---|
| 複製原文欄位（既有） | 每筆切片附帶 original_text 等完整欄位，使用不衝突名稱 |
| 額外保留原文 Chunk（新增） | 除切片外，額外輸出一筆完整來源文字的 Chunk；預設關閉 |

「原文」是當前 Unit／切分任務的完整 split_field，不跨 Units 拼成整份文件。額外 Chunk 的主要內容放該任務 output_field（預設 text），title／page 等依相同 copy 規則，繼承合法文件 metadata，建立必要 chunk_id，vectors={}；_rag 仍依 D-52 選填，不新增必要根欄位或 chunk_kind。

若本 Unit／任務已有與完整原文相同的切片，直接沿用，不重複新增。此判斷只在同一 Unit／任務內進行，不對不同文件／Units 任意去重。判斷與輸出順序須穩定；具體 Config 欄位及 ID/helper 的編排細節待核定。

延續 17 的字元教學例（不改正式 Tokenizer 計量）：

| 頁碼 | 一般切片 | 開啟後額外原文 Chunk |
|---|---|---|
| 1：7 字 | 清潔前先斷電。 | 不新增，已有完整相同內容 |
| 2：15 字 | 每月清潔散熱孔並檢查／風扇運轉。 | 每月清潔散熱孔並檢查風扇運轉。 |

因此關閉時 3 筆，開啟時 4 筆。passthrough 已完整轉出原文時，同樣不額外重複新增。多任務仍依各任務處理，不做跨任務／跨 Unit 合併。

新增的原文 Chunk 照常通過 9.1 的內容組合、Embedding 與 Indexing。完整原文可能超過模型輸入上限，須報錯／依既定失敗政策處理，不默默截斷或自動跳過。開關變更會改變 Chunk 集合，需重新 Ingestion；舊資料清除與發布沿用 Q-008～Q-010／Q-015。

<a id="src-15-93-待實作與驗收"></a>
### 待實作與驗收

- UIB-018 記錄模板表單、衍生欄位 Picker／預覽／映射與驗證；UIB-019 記錄原文欄位／原文 Chunk 的獨立選項、去重說明與數量示例。
- Prototype v0.12 已有字串模板／控制項、欄位 Picker 與每 Unit／task 的原文 3／4 筆教學預覽，完成範圍見 Builder UI／Backlog手冊。尚未實作真實 Tokenizer／Chunker、模型長度檢查與模型／DB 串接；17 的三筆教學資料不因此變成正式切分驗收證據。
- 驗收需涵蓋預設關閉、Create／Edit／AI／匯出一致、缺欄位／輸出衝突、衍生來源向量綁定、完整原文重複判斷、單／多 Unit 與多任務、Token 超長及設定變更重跑影響。正式 Schema／模板細節留 Q-002／Q-003／Q-004／Q-015。

<a id="inference-state-draft"></a>
<a id="query-context-contract"></a>
<a id="inference-kiss-discussion"></a>

<a id="src-05-46-querycontextresultsetresultitem已確認的簡化-contract"></a>
## Inference：QueryContext／ResultSet／ResultItem

機器定義：[inference_context.schema.json](../schemas/inference_context.schema.json)；新的 $id 為 query-context-list-0.3-draft。檔名保留供既有連結使用，root 已明確改成 array。驗證時註冊共用 Chunk Schema，不由 Schema ID 自動下載。Pydantic 與連續範例見 資料契約。

<a id="src-05-461-欄位"></a>
### 欄位

```python
class FilterCondition(BaseModel):
    field: str
    operator: Literal["eq", "in"]
    value: str | list[str]  # eq 為字串；in 為非空字串陣列

class ResultItem(BaseModel):
    chunk: Chunk
    score: FiniteFloat | None = None

class ResultSet(BaseModel):
    key: str
    items: list[ResultItem] = Field(default_factory=list)

class QueryContext(BaseModel):
    ori_query: str
    query: str
    filters: list[FilterCondition] = Field(default_factory=list)
    result_sets: list[ResultSet] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

contexts: list[QueryContext] = [QueryContext(ori_query="設備多久保養？", query="設備多久保養？")]
```

識別字／問題非空；score 只接受有限數值或缺省／null。filters、result_sets、metadata 可省略，載入時預設 []／[]／{}。公開 Model 拒絕未知頂層欄位。具體型別與跨欄位驗證以可執行 Model 為準。

<a id="src-05-462-keyfilter-與-metadata"></a>
### key、Filter 與 metadata

- ResultSet.key 是穩定的 Config 路徑／群組名稱，如 text_bm25、text_vector、merged；可用於選取與來源權重，不是 log-only。每個 QueryContext 內須唯一；不同 Query 可沿用相同 key。
- API 的 filters 與 System 預設條件全部 AND，放入初始 QueryContext.filters。Rewrite 複製它，不讓 LLM 產生或改寫。只允許已建索引的過濾欄位及 eq／in；範圍語意不在此擴充。
- metadata 預設 {}，承載 language、session_tag 等 JSON；不是 Config、Secret 或授權來源。Rewrite 複製，Rerank／Top N 保留。
- 同一次請求的跨 Query 合併才合法；filters 必須相同。本版參考實作要求 metadata 相同，衝突明確報錯，不任意選最後一筆。真正 request／ACL 身分由可信執行 Context 管理，不能只比較 ori_query 就當成同次請求。

<a id="src-05-463-分數與共同排序"></a>
### 分數與共同排序

| 操作 | 當前有效輸出 |
|---|---|
| Retrieval | 有序 items；Adapter 將距離等數值轉為越大越好，無數值可省 score |
| RRF | 用每份清單 1-based 陣列位置：sum(1/(k+position))；結果寫入 score |
| Sum Score | 所有分數存在，且 Config 明確確認可比或提供支援的正規化；否則拒絕 |
| Rerank | 新模型分數覆寫 score，再排序及 Top N，不保留舊分數欄位 |
| Top N | 保留已排序清單前 N；不夠不補，空清單合法 |

不能把 score 寫成名次再當相關分數加總；排名已由 items 位置提供。較低距離較好的後端由 Adapter 轉換，不新增 score_order。不同來源即使都越大越好，尺度也不一定可比。同分決勝正式政策仍見 Q-011／Q-014；參考程式以 chunk_id 穩定決勝，不因此凍結所有 Component。

<a id="src-05-464-合併與當前狀態"></a>
### 合併與當前狀態

同 Query 多路合併替換該 context 的 result_sets。跨 Query 依相同 key／路徑群組處理；完成後可輸出一筆 context（query 回到 ori_query），保留未合併的其他分組。merge_key 僅 chunk_id／document_id：前者對齊同一 Chunk，後者在融合後以最高分 Chunk 代表同文件，不把同文件不同 Chunk 分數盲目加總。rank-only 的文件代表以既有排序位置選取；需跨清單比較時先建立可比較順序／融合分數。

若 ES 已內部 Sum Score／RRF，只回傳一份 key=es_hybrid 的清單與最終 score；不捏造 BM25／Vector 的分項清單、分項分數或排名。需要分路結果時 Adapter 必須真的取得各路輸出。

<a id="src-05-465-五個完整例子與-python"></a>
### 五個完整例子與 Python

| 案例 | 檔案 | 讀法 |
|---|---|---|
| 多路檢索 | [01_retrieval.json](../examples/inference/01_retrieval.json) | 每 Query 多個 key／items |
| Top N 後 | [02_top_n.json](../examples/inference/02_top_n.json) | 只留當前有效候選 |
| Rerank 後 | [03_rerank.json](../examples/inference/03_rerank.json) | 目前分數與順序，沒有歷史清單 |
| 跨 Query 融合 | [04_cross_query_fusion.json](../examples/inference/04_cross_query_fusion.json) | 合併後 context，metadata 保留 |
| ES Hybrid | [05_es_hybrid.json](../examples/inference/05_es_hybrid.json) | 一份後端融合輸出 |

[python_example.py](../examples/inference/python_example.py) 示範 RRF、Top N、同／跨 Query 合併與替換評分；不呼叫模型或資料庫。完整 DTO 例子見 資料契約手冊。UI 仍是固定示意候選，不以計畫預覽冒充真實執行。

<a id="src-05-466-明確遷移"></a>
### 明確遷移

舊 InferenceState、query_id／ori_query_id、active_*、result_set_id、stage、operation、source、score_kind／score_order、ResultItem.rank／source_refs 不再是這版業務物件欄位。舊 wrapper 不靜默接受；呼叫端及 Remote Service 須同步升級 Contract。Chunk.metadata._rag 未被刪除，仍是不同責任的選填文件追溯。

Config、資源與可信授權由 Runtime 注入，不因移除記錄欄位而失去控制；正式 HTTP 版本協商、錯誤及 SDK 發布仍依 Q-002／Q-019。兩層合併與四處 Top N 見 [Builder UI／Backlog](07_builder_ui.md)。

<a id="src-05-65-過濾條件"></a>
## FilterCondition 與條件合併

```json
[{"field":"metadata.department","operator":"eq","value":"manufacturing"}]
```

Indexing 宣告可過濾欄位；Retrieval 保存預設條件；Query API 可加本次條件。全部與後端強制授權 AND；in 清單內為任一值符合。第一版 eq 為非空字串，in 為非空、不重複字串清單。空條件清單不增加業務限制，不能取消 ACL。

所有 Query × 欄位路徑須在取 Top-K 前套用相同限制。缺值／null／多值精確語意與 Adapter 可用能力見 Q-013；不支援就拒絕配置。數值／日期／OR 群組列為後續。

<a id="src-19-1-決策與責任"></a>
## IndexBinding：決策與責任

每個 Retrieval System 第一版只有一組邏輯索引，省略 index_ref，不提供多組選擇／管理。多個全文／向量欄位，以及 Component 內部的多個 FAISS Index，可由這組統一管理。

Indexing Component 提供索引描述，Engine 補足可信執行環境、驗證並管理 Binding，Retrieval 透過 Context 取得該 System 唯一的 Binding。Binding 對應整組索引，不為每個 Chunk／Query 各建立一份。一般 Builder User 不另外填 Binding。

| 資訊 | 責任 |
|---|---|
| Component Config | 方法、搜尋／索引欄位、Top K 等處理設定，由 Schema 驗證 |
| 部署設定 | 環境 URL、Secret 引用與資料目標 |
| IndexBinding | 索引格式、定位資訊及經驗證的搜尋能力 |
| RunContext | Engine 提供的必要資源／Binding 引用；與業務 QueryContext 不同 |
| Runtime 狀態 | 初始化／就緒／失敗與資料發布狀態；精確政策依 Q-009／010／017 |

RunContext 的資源由 Config、部署綁定及 Runtime 初始化共同準備，不是 Component Config 的別名。Client、FAISS／BM25 物件留在執行程序中，由 Engine 管生命週期與共用；每次查詢不必重建。Remote Adapter 不將完整 Context／憑證傳給服務，僅傳核定業務資料及明確支援參數。

<a id="src-19-2-共用-schema"></a>
## IndexBinding：共用 Schema

```python
class VectorIndexBinding(BaseModel):
    embedding_profile_id: str
    source_field: str
    dimensions: int  # 正整數

class IndexBinding(BaseModel):
    artifact_type: str
    target: dict[str, JsonValue] = Field(default_factory=dict)
    fulltext_fields: list[str] = Field(default_factory=list)
    filter_fields: list[str] = Field(default_factory=list)
    vector_bindings: dict[str, VectorIndexBinding] = Field(default_factory=dict)
```

完整嚴格 Model 見 examples/pydantic_contracts/models.py；共用機器 Schema 見 [index_binding.schema.json](../schemas/index_binding.schema.json)。識別／路徑字串非空、維度正整數，欄位清單不重複，未知外層欄位拒絕。artifact_type 必填；其餘四欄可省略，預設為空 object／清單。target 只能含 JSON 資料，不能放 Client、Python class 或任意 import。

| 欄位 | 語意 |
|---|---|
| artifact_type | 已註冊索引格式及版本；識別格式，不是 Component 實作版本 |
| target | 格式專屬的定位資訊，依對應 Schema 再驗證 |
| fulltext_fields | 已提供全文搜尋能力的完整欄位路徑，如 fields.text |
| filter_fields | 已提供 Filter 能力的路徑，如 metadata.department；運算子／缺值政策另依 Q-013 |
| vector_bindings | key=text 表示 vectors.text；Profile、來源欄位及維度必須相容 |

source_field=text 對應 Chunk.fields.text，與既有 DenseVector 一致。Binding 宣告可用能力，Retrieval Config 只能選其中支援者；Chunk 保存某個欄位不代表該欄位可搜尋。宣告、Config、向量與格式需驗證一致，不能只靠宣告通過就假定後端真的有能力。

不保留舊提案的 index_ref、backend、capabilities、system_id、contract_version 或 searchable；共用能力由欄位／向量資訊表達，System 由可信 Context 定位。外層 Schema 版本由 SDK／協定管理，不與 artifact_type 的儲存格式版本混同。index_generation／mapping_version／document_schema_version 等暫不列本版必填，交 Q-007～010／Q-015 決定，沒有取消索引相容性與資料版本管理。

<a id="src-19-3-索引格式定義與-developer-配套"></a>
## IndexBinding：索引格式定義與 Developer 配套

artifact_type 對應一份受控註冊的「索引格式定義」，包含 target Schema、資料儲存／讀取規格及能力限制。Indexing／Retrieval 共用這份規格；只有 Binding 無法說明資料布局或如何還原 Chunk。

| 定義 | 第一版示例 |
|---|---|
| builtin.elasticsearch/v1 | target={"collection":"workspace-system-a"}；collection 為 ES 實體索引／約定目標名稱 |
| builtin.local_search/v1 | target={}；唯一索引資源由 System Context 取得，不再引入 resource_ref |

兩個名稱是本次可執行範例的格式識別。target Schema 已提供；完整 ES 儲存 Mapping／Chunk 還原、Local 索引布局／Filter 實作與 Query Encoding 資源介面，仍須於 Q-002／Q-003／Q-011／Q-013 落實並驗收，不能以 target 形狀通過就宣稱格式已完整實作。

相容性流程：核可格式註冊 → Indexing 宣告產出格式 → Retrieval Descriptor 宣告支援格式／版本 → Engine 驗證 target、格式配對、搜尋欄位及 Profile → 檢查 Runtime 就緒／授權 → 執行。未註冊、格式錯版、不相容或未宣告的搜尋欄位應拒絕，不靜默換方法。正式 Descriptor 欄位拼字／版本範圍留 12／Q-019／Q-028。

Developer 可沿用既有格式只開發 Retrieval；若產出新格式，須提供格式規格／Schema，並提供相容 Retrieval 或 Adapter。註冊資料不載入任意前端程式或 import 指令。配套包含：共用 Model、格式規格、Retrieval 範本／資源取得說明及契約／整合測試。

[artifact_definitions.json](../examples/pydantic_contracts/artifact_definitions.json) 示範兩種格式的 target Schema；它不是已定案的 Manifest Meta-schema 或 Registry API。validate_binding_format 是離線註冊／配對驗證參考，不是已交付 Engine。

<a id="src-19-4-範例"></a>
## IndexBinding：範例

```python
es_binding = IndexBinding(
    artifact_type="builtin.elasticsearch/v1",
    target={"collection": "workspace-system-a"},
    fulltext_fields=["fields.text", "fields.title"],
    filter_fields=["metadata.department"],
    vector_bindings={
        "text": VectorIndexBinding(
            embedding_profile_id="embedding-v1",
            source_field="text",
            dimensions=1024,
        )
    },
)

local_binding = IndexBinding(
    artifact_type="builtin.local_search/v1",
    target={},
    fulltext_fields=["fields.text"],
    vector_bindings=es_binding.vector_bindings,
)
```

同樣的 Profile／欄位可由不同後端實作，但兩種 artifact_type 不能任意交叉讀取。實際宣告 Filter 前需提供可靠候選過濾能力。Profile 相容不只比較維度，仍需配對模型版本及 Query／Document Encoding。

<a id="src-19-5-狀態保存與待決邊界"></a>
## IndexBinding：狀態、保存與待決邊界

Binding 存在不代表可以查詢。searchable 已移出 Binding；初始化中、恢復中、失敗等由 Runtime 管理。工作 API 是否另外投影 searchable 布林值仍屬 Q-019，不等於把它放回 Binding。

依恢復需要保存或重建可序列化描述，不保存 Client／FAISS Python 物件。Memory 重啟需重新 Ingestion；MongoDB 保存完整 Chunk／vectors，重建本地搜尋資源，完成後才能依發布政策就緒。保存描述不能代替原始資料、Profile、版本及完整性驗證；精確 MongoDB Manifest 與恢復流程仍在 Q-012／Q-015。

本次定案為單組邏輯索引、輕量 Binding、格式專屬 Schema、能力宣告、相容 Retrieval 及狀態分離。完整 Config／SDK、API／Remote 協定、資料更新／失敗清理／最終可見性、同分／Filter 語意及版本遷移仍依 08 的 Q-ID，不因本次拍板一併關閉。

<a id="src-19-6-d-58文件存在清單與直接刪除"></a>
## IndexBinding：D-58：文件存在／清單與直接刪除

Document 管理使用同一 System 的儲存／索引範圍，不新增第二組 Binding。需依 Artifact 的資料布局，查 document_id 是否有目前有效資料、去重分頁列出全部 ID，以及刪除該文件的 Chunk／vectors、搜尋索引和供恢復的持久副本；不能只刪 FAISS／記憶體索引卻保留 MongoDB 資料，導致重建復活。

預設保存的是 Chunk，document_id 不是 chunk_id／ES _id 的別名；不能只刪掉單一同名 Chunk 就宣稱文件已退役。Runtime 的工作狀態不是文件目錄；清單／存在查詢讀取實際後端，失敗需回錯誤。

新格式／相容 Adapter／私有 Remote 需說明三種管理操作的支援方式與測試，精確介面／能力宣告待 SDK／Manifest 核定；不增加 IndexBinding 根鍵或一般 User 要填的管理參數。API 與語意見 [Runtime API](06_runtime_api_and_deployment.md#src-21-9-文件資料查詢與直接刪除)。


D-60：平台不加「寫入時阻擋 Query」的讀寫鎖／全索引快照，接受更新中查到暫時新舊混合。此規則也適用文件存在／ID 清單的當前可見資料；工作成功／失敗與資料存在分開。retire 完成後新的讀取應反映刪除，但已取候選的在途 Query 可仍回舊資料。實體 backend 可見性／錯誤清理需驗證，不新增 Binding 狀態鍵。


<a id="src-19-d-65文件摘要的儲存管理能力"></a>
### D-65：文件摘要的儲存管理能力

Runtime 文件清單回傳 documents[]，每筆 document_id＋source_revisions[]，完整定義引用 [Runtime API](06_runtime_api_and_deployment.md#src-21-2-api-清單7-支業務-api2-支-health-api)。Storage／Index Adapter 從實際 Chunk 去重彙整，不以工作完成紀錄代替，也不任取某個 Chunk 的版本充當文件最新版本。私有 Remote Indexing／儲存服務需有等價受控管理操作；完整 SDK／HTTP 操作格式仍待 Q-028，不要求無狀態 Parser／Embedding／Rerank 實作。

source_revisions 是 API 摘要，不把 Chunk.source_revision 改為陣列、不新增 IndexBinding 根鍵或 Pipeline Module，也不要求持久保存 ParsedDocument。ES 聚合或 Local 對照必須能完整列出該文件實際存在的版本，不能將 backend 預設截斷的子聚合當成完整清單；具體讀取與容量實作待驗證。

<a id="src-17-2-逐型別範例"></a>
## Python／Pydantic：完整連續範例

先安裝 requirements.txt，再把 typed_examples.py 的範例依序執行。匯入、Annotated／Literal／Field 等別名見 models.py。分頁解析、UI Backlog手冊 字元切分、向量及分數都是教學資料；沒有執行 Parser／Tokenizer／模型。主案例省略 _rag。

<a id="src-17-21-ingestiondocument"></a>
### IngestionDocument

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class IngestionDocument(BaseModel):
    document_id: NonEmptyText
    source_revision: NonEmptyText | None = None
    content: NonEmptyText | ContentObject | None = None
    base64: NonEmptyText | None = None
    uri: NonEmptyText | None = None
    media_type: NonEmptyText | None = None
    schema_id: NonEmptyText | None = None
    parsing_profile: NonEmptyText | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

<!-- type-example:IngestionDocument:start -->
```python
ingestion_doc = IngestionDocument(
    document_id="manual-001",
    source_revision="v1",
    content={
        "title": "設備保養手冊",
        "text": "=== PAGE 1 ===\n清潔前先斷電。\n=== PAGE 2 ===\n每月清潔散熱孔並檢查風扇運轉。",
    },
    media_type="application/json",
    metadata={"department": "製造部", "filename": "maintenance.txt"},
)
```
<!-- type-example:IngestionDocument:end -->

<a id="src-17-22-parseddocument"></a>
### ParsedDocument

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class ParsedDocument(BaseModel):
    document_id: NonEmptyText
    source_revision: NonEmptyText
    units: list[dict[str, JsonValue]] = Field(min_length=1)
    metadata: dict[str, JsonValue]
```

<!-- type-example:ParsedDocument:start -->
```python
# 示意 Parser 識別分頁標記後的輸出；不是直接呼叫 Parser。
parsed_doc = ParsedDocument(
    document_id=ingestion_doc.document_id,
    source_revision=ingestion_doc.source_revision,
    units=[
        {"text": "清潔前先斷電。", "title": "設備保養手冊", "page": 1},
        {"text": "每月清潔散熱孔並檢查風扇運轉。", "title": "設備保養手冊", "page": 2},
    ],
    metadata=ingestion_doc.metadata.copy(),
)
```
<!-- type-example:ParsedDocument:end -->

<a id="src-17-23-chunk"></a>
### Chunk

承接上面的兩頁 ParsedDocument；7 字元與 15 字元，每 10 字元切一組，overlap=0，明列三筆 Chunk(...)。字元示意不是 Tokenizer。

```python
class Chunk(BaseModel):
    chunk_id: NonEmptyText
    document_id: NonEmptyText
    source_revision: NonEmptyText
    fields: Annotated[dict[NonEmptyText, JsonValue], Field(min_length=1)]
    metadata: dict[str, JsonValue]
    vectors: dict[NonEmptyText, DenseVector]
```

<!-- type-example:Chunk:start -->
```python
# 將上一個 ParsedDocument 逐 Unit、每 10 字元切分，overlap=0。
# 以下直接列出三筆結果；尚未執行 Embedding，主範例省略 _rag。
chunks = [
    Chunk(
        chunk_id="chunk-demo-001",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "清潔前先斷電。",
            "title": "設備保養手冊",
            "page": 1,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
    Chunk(
        chunk_id="chunk-demo-002",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "每月清潔散熱孔並檢查",
            "title": "設備保養手冊",
            "page": 2,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
    Chunk(
        chunk_id="chunk-demo-003",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "風扇運轉。",
            "title": "設備保養手冊",
            "page": 2,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
]

# 後面的 ResultItem 等範例，以第一筆 Chunk 示範。
chunk = chunks[0]
```
<!-- type-example:Chunk:end -->

<a id="src-17-24-densevector"></a>
### DenseVector

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class DenseVector(BaseModel):
    values: Annotated[list[FiniteFloat], Field(min_length=1)]
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText
```

<!-- type-example:DenseVector:start -->
```python
vector = DenseVector(
    values=[0.1, 0.2, 0.3],  # 教學用三維值；正式維度由模型決定。
    embedding_profile_id="embedding-demo-v1",
    source_field="text",  # 來源是 Chunk.fields.text。
)
```
<!-- type-example:DenseVector:end -->

<a id="src-17-25-filtercondition"></a>
### FilterCondition

eq 必須為字串；in 必須為非空字串陣列，並由 Runtime 驗證欄位有相容 Filter 索引。

```python
class FilterCondition(BaseModel):
    field: NonEmptyText
    operator: Literal["eq", "in"]
    value: str | list[str]
```

<!-- type-example:FilterCondition:start -->
```python
filter_condition = FilterCondition(
    field="metadata.department", operator="eq", value="製造部",
)
```
<!-- type-example:FilterCondition:end -->

<a id="src-17-26-resultitem"></a>
### ResultItem

score 選填，可缺省／null；只有數值時為越大越好。RRF 直接讀 items 的位置，不能把名次塞進 score 當相關分數。

```python
class ResultItem(BaseModel):
    chunk: Chunk
    score: FiniteFloat | None = None
```

<!-- type-example:ResultItem:start -->
```python
result_item = ResultItem(chunk=chunk, score=0.95)
# 沒有數值分數的後端也合法：ResultItem(chunk=chunk)。RRF 讀取陣列位置。
```
<!-- type-example:ResultItem:end -->

<a id="src-17-27-resultset"></a>
### ResultSet

key 在同一 context 內唯一，可對應 Config 路徑或群組；items 順序就是排名。

```python
class ResultSet(BaseModel):
    key: NonEmptyText
    items: list[ResultItem] = Field(default_factory=list)
```

<!-- type-example:ResultSet:start -->
```python
result_set = ResultSet(key="merged", items=[result_item])
# key 是 Config 可引用的搜尋路徑／群組；items 順序就是排名。
```
<!-- type-example:ResultSet:end -->

<a id="src-17-28-querycontext"></a>
### QueryContext

filters／metadata／result_sets 可省略，預設 []／{}／[]。Rewrite 複製 filters／metadata；只留目前有效清單。

```python
class QueryContext(BaseModel):
    ori_query: NonEmptyText
    query: NonEmptyText
    filters: list[FilterCondition] = Field(default_factory=list)
    result_sets: list[ResultSet] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

<!-- type-example:QueryContext:start -->
```python
query_context = QueryContext(
    ori_query="清潔前應注意什麼？",
    query="清潔前應注意什麼？",
    filters=[filter_condition],
    result_sets=[result_set],
    metadata={"language": "zh-TW", "session_tag": "demo"},
)
```
<!-- type-example:QueryContext:end -->

<a id="src-17-29-chunksourceref"></a>
### ChunkSourceRef

選填的文件來源位置，與已刪除的 ResultItem 分數血緣不同。Component 沒提供時不捏造，也不阻擋處理。

```python
class ChunkSourceRef(BaseModel):
    unit_index: NonNegativeInt
    field: NonEmptyText
    output_field: NonEmptyText
    role: Literal["split", "copy"]
    start: NonNegativeInt | None = None
    end: NonNegativeInt | None = None
    chunk_start: NonNegativeInt | None = None
    chunk_end: NonNegativeInt | None = None
```

<!-- type-example:ChunkSourceRef:start -->
```python
chunk_source_ref = ChunkSourceRef(
    unit_index=0,
    field="text",
    output_field="text",
    role="split",
    start=0,
    end=len(parsed_doc.units[0]["text"]),
)
```
<!-- type-example:ChunkSourceRef:end -->

<a id="src-17-210-chunkingidentity"></a>
### ChunkingIdentity

fingerprint／ordinal／task_id 只在 Component 選擇提供時存在；SDK helper 可協助，不強迫所有 Component 實作。

```python
class ChunkingIdentity(BaseModel):
    chunking_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    chunk_ordinal: NonNegativeInt
    task_id: NonEmptyText
```

<!-- type-example:ChunkingIdentity:start -->
```python
chunking_identity = ChunkingIdentity(
    chunking_fingerprint="0" * 64,  # 實際值須依 15 的規則產生。
    chunk_ordinal=0,  # 此切分任務中的第 1 筆，從 0 起算。
    task_id="text",  # 此例設定的切分任務識別。
)
```
<!-- type-example:ChunkingIdentity:end -->

<a id="src-17-211-ragmetadata"></a>
### RagMetadata

Chunk.metadata._rag 的選填進階視圖，不改名、不增加必填頂層 key。

```python
class RagMetadata(BaseModel):
    source_refs: Annotated[list[ChunkSourceRef], Field(min_length=1)] | None = None
    chunking: ChunkingIdentity | None = None
```

<!-- type-example:RagMetadata:start -->
```python
rag_metadata = RagMetadata(
    source_refs=[
        chunk_source_ref,
        ChunkSourceRef(unit_index=0, field="title", output_field="title", role="copy"),
        ChunkSourceRef(unit_index=0, field="page", output_field="page", role="copy"),
    ],
    chunking=chunking_identity,
)
# 追溯型別的獨立進階範例；主流程 Chunk 範例省略 _rag 以利說明。
```
<!-- type-example:RagMetadata:end -->

<a id="src-17-212-vectorindexbinding"></a>
### VectorIndexBinding

與共用資料契約一致；完整限制見 Model 及主責文件。

```python
class VectorIndexBinding(BaseModel):
    embedding_profile_id: NonEmptyText
    source_field: NonEmptyText
    dimensions: PositiveInt
```

<!-- type-example:VectorIndexBinding:start -->
```python
vector_binding = VectorIndexBinding(
    embedding_profile_id=vector.embedding_profile_id,
    source_field="text",
    dimensions=3,  # 必須和 values 長度及模型輸出一致。
)
```
<!-- type-example:VectorIndexBinding:end -->

<a id="src-17-213-indexbinding"></a>
### IndexBinding

D-55 已確認。每 System 一組，無 index_ref／searchable；target 按 artifact_type 對應 Schema 驗證，Retrieval 須宣告相容格式，且只可搜尋宣告能力。完整語意與 ES／Local／客製配套見 [IndexBinding：IndexBinding 與索引格式契約](#src-19-1-決策與責任)。

```python
class IndexBinding(BaseModel):
    artifact_type: NonEmptyText
    target: dict[str, JsonValue] = Field(default_factory=dict)
    fulltext_fields: list[NonEmptyText] = Field(default_factory=list)
    filter_fields: list[NonEmptyText] = Field(default_factory=list)
    vector_bindings: dict[NonEmptyText, VectorIndexBinding] = Field(default_factory=dict)
```

<!-- type-example:IndexBinding:start -->
```python
index_binding = IndexBinding(
    artifact_type="builtin.elasticsearch/v1",
    target={"collection": "workspace-demo-system-a"},
    fulltext_fields=["fields.text"],
    filter_fields=["metadata.department"],
    vector_bindings={"text": vector_binding},
)
validate_binding_format(index_binding, ["builtin.elasticsearch/v1"])
```
<!-- type-example:IndexBinding:end -->

target Schema 與相容性驗證參考見 models.py／artifact_definitions.json；共用外層見 schemas/index_binding.schema.json。Schema 通過不是後端存在／可查詢的證據。舊 index-binding-0.1-proposal payload 需明確遷移，不靜默接受已刪鍵。

<a id="src-17-214-moduleresult"></a>
### ModuleResult

只示範本地 Parser 的成功包裝。Remote Parser body 是 ParsedDocument[]；推論業務 body 直接 QueryContext[]，不能再加 data 外框。

```python
class ModuleResult (Generic[T]):
    data: T
```

<!-- type-example:ModuleResult:start -->
```python
# 以 Parser 的本地呼叫為例；同一個 API 請求也可能解析出多份文件。
module_result = ModuleResult[list[ParsedDocument]](data=[parsed_doc])
parser_http_body = [doc.to_payload() for doc in module_result.data]
# Remote Parser HTTP 回傳 parser_http_body；本地 Adapter 再包成 ModuleResult。
```
<!-- type-example:ModuleResult:end -->

<a id="src-17-3-推論直接傳-list"></a>
## Python 推論根物件與呼叫方式

```python
from pydantic import TypeAdapter
from models import QueryContext

contexts: list[QueryContext] = [query_context]
wire = [context.model_dump(mode="json") for context in contexts]
validated = TypeAdapter(list[QueryContext]).validate_python(wire)
```

Query Transformation、Retrieval、Rerank 均用同型別，更新 filters／metadata／目前清單後傳出。Rerank 覆寫 score，結果排序後取 Top N；RRF 以 enumerate(items, start=1) 取得名次，輸出融合 score。Sum Score 必須有完整可比分數。跨 Query 僅限同次請求、相同 filters；本版 metadata 不同時拒絕合併，避免靜默覆寫。歷史或效能資料寫 Logs。

這版取代舊 InferenceState：不接受舊 wrapper，不保留 active_*、query/result IDs、operation、score_kind/order 或 ResultItem.rank/source_refs。Chunk 的選填 _rag 仍保留。

<a id="src-17-4-驗證與限制"></a>
## 資料測試、重現方式與限制

```bash
python -m pip install -r examples/pydantic_contracts/requirements.txt
python examples/pydantic_contracts/build_examples.py
python examples/pydantic_contracts/export_schemas.py
python examples/pydantic_contracts/test_models.py
python examples/inference/python_example.py
```

[examples.json](../examples/pydantic_contracts/examples.json) 提供 14 個型別例子、三筆 Chunk、QueryContext[] 與 Parser 成功包裝。五組完整推論快照見 examples/inference。DTO 型別檢查不代替業務規則：索引可用性、授權、向量 Profile、分數可比性、模型上限仍需 Runtime／Adapter 驗證。正式 SDK 版本與錯誤政策由 計畫與決策手冊 追蹤。

## Schema 與業務欄位的責任

共用 Contract 固定外層；Component 宣告＋有效 Config 提供內部欄位細節。取消獨立頂層 document_schema；必要時由 Parser 的參數接受 User 欄位定義。這個解析結果供資料驗證與下游 Picker，仍須在實際執行時驗證資料。

來源／Chunk ID、缺值、metadata 保留區、Filter 精確語意、Tokenizer 與版本凍結等未決政策集中在計畫手冊 Q-002～Q-015，不由資料範例偷定案。驗證通過不表示真實 Parser／模型／索引已整合。


<a id="embedding-profile"></a>
## Embedding Profile 與 Document／Query 配對

Embedding Profile 的必要語意包含：模型／版本、維度、document／query encoding、normalization、Tokenizer／revision。Document 與 Query 向量必須用相容 Profile 配對；只換服務 URL 不代表模型語意可任意改變。

IndexBinding 由 Indexing 提供，Retrieval 經可信 Context 使用；只可搜尋宣告且相容的能力。Chunk 有保存某欄位不表示已建立該欄位的搜尋索引。維度與來源欄位等細節沿用前面的向量／Binding 規格，正式 Profile 格式仍待 Q-003／DS／SC 收斂。


<a id="parsed-document-migration"></a>
## ParsedDocument 格式遷移

0.2 是不相容草案變更：移除舊頂層 fields／structure，替換為 units；不以別名靜默兼容。舊結構如何展平由 Parser／Adapter 決定，不能只改鍵名丟掉邊界／上下文。Chunk SourceRef 同步升為 0.2，Inference 引用同一版本。

Parser／展平策略改動可能改變 Unit 順序、切片及索引，需重新 Ingestion。相同 source_revision 下 Parser 版本變化的 identity／發布政策仍在 Q-007／Q-008，不以 unit_index 解決版本衝突。

UI 預覽、欄位候選、Header-aware 條件與舊結構路由移除列入 [UIB-014](07_builder_ui.md#uib-014-flat-units)，原型已有相關模擬，正式 Parser／Adapter 與遷移仍需驗證。


<a id="contract-test-commands"></a>
## 契約重現與文件產生工具

共用來源、資料驗證與實際演算法／模型驗收分開。以下工具使用既有固定測資，不代表正式 Engine 已完成：

| 範圍 | 指令（repo 根目錄） |
|---|---|
| ParsedDocument | python examples/parsed_document/test_contract.py |
| Chunk | python examples/chunk/test_contract.py |
| 共用 Pydantic／Inference／Binding | python examples/pydantic_contracts/test_models.py |
| Descriptor 候選 | python examples/component_descriptor/validate_examples.py |
| Parser Local／Remote 教學 | python examples/component_development/test_demo.py |

依各 examples 的 requirements 安裝依賴。examples/contracts/render_classification_examples.py 與 examples/chunk/render_report.py 只更新本手冊標記的範例區塊；examples/pydantic_contracts/export_schemas.py 依 Model 產出 Schema／Artifact 目錄。產生器路徑已對齊新手冊，重新產生時保留穩定連結錨點。

未知 Token Usage 不填 0；Secret／可信 ACL 不混入文件資料或診斷。實際提交、恢復、Provider 與部署驗收仍依各主責手冊及 Q-ID。
