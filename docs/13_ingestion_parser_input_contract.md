# Ingestion API／Parser 共用輸入 Contract

> 2026-11-05 D-58：Runtime POST /v1/ingestions 統一接收非空 IngestionDocument[]，單筆也包 List；**每個 item 與 Parser input 共用本文件的單筆 Schema**。HTTP 批次容器不傳入 Parser；本文單物件範例仍是文件 item，不是完整 HTTP body，完整提交見 [21](21_runtime_ingestion_inference_api_inventory.md)。

> 2026-11-03 D-52：API／Parser Input 的根結構不變；合法 metadata 可含 Component 支援的文件層處理提示，例如 chunking_mode=passthrough。須符合共用 Contract 及適用 Component 的 metadata 細節宣告／設定，由對應 Component 說明讀取與預設行為（D-67 不再獨立頂層 document_schema），不是全域覆寫 Config 的入口；_rag 追溯由輸出 Component 選填。見 [15 §4.1](15_chunk_contract.md)。

> 2026-10-29（Asia/Taipei）· 共用輸入 Schema 與語意已確認（D-44／D-45）；尚未實作 API／SDK；批次容器已由 D-58 確認非空 List，版本生成與執行細節另議。
>
> 本文記錄 JSON-only、扁平輸入、多 Parser 自動路由，以及使用者確認「Ingestion API 與 Parser Input 使用相同 Schema」。共同物件稱 IngestionDocument；不另設另一份公開 ParserInput。解析後輸出依 [14 ParsedDocument](14_parsed_document_contract.md)，切分後依 [15 Chunk](15_chunk_contract.md)；三者各有共用 Schema，不混用輸入與輸出欄位。

## 0. 情境整理與分類總覽（報告摘要）

**這份文件整理的是「各種來源的資料，如何透過同一個入口交給 Retrieval Engine Library」**。使用者可以送簡單文字、結構化紀錄、原始文件，或已被其他工具解析好的內容；平台統一接收 JSON，由相容 Parser 處理，不要求所有呼叫端先完成同樣程度的解析。

### 0.1 從哪些使用情境整理而來

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

### 0.2 分類結果：傳入方式、內容格式、處理程度分開看

| 分類維度 | 分類結果 | 對設計的影響 |
|---|---|---|
| **怎麼取得內容** | content 直接內容／base64 編碼檔案／uri 資源引用，三選一 | 決定直接讀取、解碼或下載，不決定要用哪個解析演算法 |
| **內容是什麼格式** | 文字、JSON、PDF、PPTX、Excel、圖片等 | 依 media_type、必要 schema_id 及實際內容，驗證是否有相容 Parser |
| **已經處理到哪一步** | 未解析內容／上游已解析內容 | 前者解析來源；後者驗證與轉換，不強迫全部重新解析 |

三個維度可以組合，例如「透過 URL 提供已解析 JSON」或「用 Base64 提供原始 PDF」。多個 Parser 的用途是提供相容路徑，不是讓每筆資料依序執行全部 Parser。API 及 Parser 共用 IngestionDocument；內容取得使用 SDK 共用資源，不另維護第二份輸入 Schema。

<!-- classification-examples:ingestion:start -->

以下是符合目前 IngestionDocument 外層 Schema 的單筆例子，與 Parser Input 使用同一份契約。例子由 [共用資料來源及產生工具](../examples/contracts/render_classification_examples.py) 驗證／產生，資料見 [report_cases.json](../examples/contracts/report_cases.json)；此處驗證資料形狀，尚未執行 API。

#### 0.2.1 content：直接傳文字

只有文件 ID 與內容即可表達最簡單情境；相容 Parser 產生 ParsedDocument。

```json
{
  "document_id": "manual-001",
  "content": "清潔前先斷電。"
}
```

#### 0.2.2 content：直接傳多欄位 JSON

這是一筆文件的原文、標題與既有摘要；metadata 另外保存部門。CSV 映射後也可形成這種單筆資料。

```json
{
  "document_id": "manual-001",
  "content": {"text": "清潔前先斷電。", "title": "設備手冊", "summary": "清潔前的安全步驟"},
  "metadata": {"department": "engineering"}
}
```

#### 0.2.3 base64：傳送編碼後的檔案內容

用短文字檔示範 Base64，實際可解碼為「清潔前先斷電。」。PDF／PPTX／Excel 使用相同傳輸欄位，須填入完整檔案內容、正確 media_type 並有相容 Parser。

```json
{
  "document_id": "manual-file-001",
  "base64": "5riF5r2U5YmN5YWI5pa36Zu744CC",
  "media_type": "text/plain"
}
```

#### 0.2.4 uri：取得 URL 指向的檔案

只傳資源位置，由共用能力取得 PDF，再交給相容 Parser；這個示意網址未進行下載／連線驗證。

```json
{
  "document_id": "report-001",
  "uri": "https://storage.example.com/report.pdf",
  "media_type": "application/pdf"
}
```

#### 0.2.5 content：上游已整理好的 Units

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

### 0.3 責任分工與目前範圍

| 層級 | 責任 |
|---|---|
| Retrieval Builder／自行部署的呼叫端 | 提供方便的上傳／映射／檔案傳輸轉換；組成 JSON |
| Engine 的共用入口／SDK 資源能力 | 驗證共同外層、授權取得內容、解碼及必要限制；路由到已設定的 Parser |
| Parser／Adapter | 理解來源或轉換已解析資料，產出統一 ParsedDocument，詳見 [14 的情境與結構分類](14_parsed_document_contract.md#0-情境與分類結果報告摘要) |

JSON-only、扁平輸入、三種來源、API／Parser 共用契約與多 Parser 路由方向已確認；API／SDK 尚未實作，實際格式需有相容 Component 才可執行。單筆外層 Schema 與 D-58 的 List 接收格式已確認；D-64 的 Runtime 初始大小／文件數限制已集中在 22；來源版本生成、逐 Provider／Client 限制與正式供應者支援仍依正文核定。直接匯入最終 Chunk／vectors 另外討論，不混入「上游已解析」的支援承諾。

## 1. 已確認方向與責任

- Engine Runtime 的 Ingestion API 只接收 JSON body。Retrieval Builder 可提供文件／CSV 上傳及轉換；自行部署的呼叫端自行完成相同傳輸前處理，不要求部署 Builder。
- JSON 支援 inline 文字／物件、Base64 檔案與資源 URI。傳輸前處理不等於語意解析；原始 PDF 等內容仍由 Engine 的相容 Parser 處理。
- Payload 採扁平格式，不需要 source 或 mode；content／base64／uri 三選一。
- **API 單筆文件與 Parser Input 共用 IngestionDocument 及同一份 JSON Schema**；Parser 可接收經共同驗證／反序列化的 SDK 物件，但欄位、型別與驗證規則一致，不維護第二份轉換後的輸入 contract。
- 接受未解析內容與上游已解析內容；後者由相容 Parser／Adapter 驗證及正規化，不強制重做解析。這不等於已核可直接匯入 Chunk／vectors。
- Parsing 可啟用多個 Parser，平台依能力自動路由；格式不重疊時不要求使用者配置 Router。同格式衝突才需預設策略或進階 parsing_profile。
- 沒有相容 Parser、路由歧義、格式與實際內容不符時明確報錯，不以載入順序選第一個，不默默改用其他 Parser。

## 2. 單筆文件 JSON Schema

機器可讀共同定義：[ingestion_document.schema.json](../schemas/ingestion_document.schema.json)。它是 API 與 Parser Input 的同一份外層 Schema；單位是單筆文件，不是整個批次或 HTTP 回應。最小 List item／Parser Input 為（完整 HTTP body 需包成 [此物件]）：

```json
{
  "document_id": "doc-001",
  "content": "這是文件內容"
}
```

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

D-67：Parser 的 Descriptor／Manifest 宣告共用 Input／Output 引用與固定或依 Config 細化的資料規格，見 [24](24_component_io_schema_refinement.md)。API 仍直接交相同 IngestionDocument，不新增 ParserInput。接收時可判定的路由／內容欄位可加入 202 前整批快速預檢；需下載、解碼、辨識或解析才可確認的檢查仍在背景工作，202 不表示解析成功。輸出驗 ParsedDocument 共用 Contract＋當前資料細節；不要求 User 再填一份全域 document_schema。


D-58 已確認一支 POST /v1/ingestions，body 為非空 IngestionDocument[]，單筆亦一元素 List；整批預檢通過才 202，執行逐文件結果、Run 可 partial。每筆使用本共用 Schema；完整回應／錯誤 OpenAPI 仍待整理，見 21。

## 3. 輸入範例

### 3.1 結構化 JSON

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

### 3.2 PDF 資源引用

```json
{
  "document_id": "report-001",
  "uri": "https://storage.example.com/report.pdf",
  "media_type": "application/pdf"
}
```

### 3.3 PDF Base64

```json
{
  "document_id": "report-002",
  "base64": "JVBERi0xLjcKJSVFT0YK",
  "media_type": "application/pdf"
}
```

此字串是可解碼的示意內容，不是有效 PDF 測資；必須再由 Parser 驗證檔案。Base64 約增加 1/3 傳輸體積；實際 body、解碼後檔案、下載大小及逾時上限尚未核定，不把先前提議的 5 MB 當產品限制。

### 3.4 上游已解析資料

content 可由已註冊 Adapter 接收 {"units": [...]}，驗證後搭配外層 document_id、source_revision、metadata 形成 ParsedDocument。此為已解析內容的示意 Profile，正式 schema_id 名稱仍待核定；不是直接接受 Chunk 或向量。原生供應者結構也可放 content object，但須由相容 Parser 展平為 Units。ID／metadata 重複來源需明定一致性政策，不得靜默覆寫。

## 4. 是否也是 Parser 的 Input？

**是，Ingestion API 每個 List item 與 Parser Input 共用 IngestionDocument 及相同 Schema；完整 HTTP body 是文件 List，Parser 接收其中一份文件。** 內容解碼由共用 resolver 處理，不建立另一份公開輸入契約。

### 4.1 共用物件，透過 SDK 取得內容

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

### 4.2 context 不屬於 API payload

context 是 Engine 建立的執行資源，由 Engine 傳給 Parser；呼叫端不用在 JSON 裡提供。以下為責任規劃，不表示公開 class 的屬性已凍結：

| 執行資源 | 用途 |
|---|---|
| 共用內容 resolver | URI 取得、Base64 解碼與資源限制 |
| request／run 追蹤 | 模組 Log、診斷與來源追溯 |
| 執行控制 | 必要時提供取消／逾時與資源釋放 |

Component 參數與服務設定可在建立 Instance 時注入，不必全部塞進 context。可信來源資訊、授權與 Secret 由平台資源／受控 Context 處理；不新增 API 的 source_info 欄位，不信任 metadata 覆寫可信資訊。

document_id、source_revision 及有效 metadata 持續傳遞；省略版本的生成政策仍待定。resolver 的 bytes／stream／resource handle、快取／重用、生命週期與 Context 精確介面待 Q-002／Q-016／Q-017，但「共用輸入 Schema」不再列為待決。

## 5. Parser 能力與 Chunker 相容

Parser 宣告可接受的 media_type、schema 及必要資源；多個 Parser 的啟用不代表每筆都執行全部，也不保證混合模態的聯合理解。相同格式只有一個可用實例時自動選用；有重疊時需明確預設／profile。格式副檔名僅為提示，不取代實際驗證。

ParsedDocument 使用唯一的平面 units 格式；Chunker 檢查指定字串欄位、Markdown 格式與 Tokenizer 能力，不再依 text-spans／page-blocks 配對或路由。Parser 負責將結構整理成可獨立切分的 Units；不支援的來源由 Parser 明確拒絕。詳見 [14](14_parsed_document_contract.md)。

## 6. 驗證邊界與待決事項

- API／Parser 先驗同一份 IngestionDocument 外層，再驗相容 Component 的 content／實際格式限制；支援 JSON object 不代表可匯入任意內容、Chunk 或向量。
- Parser 輸出依 [14](14_parsed_document_contract.md) 的四鍵 Units Schema 與語意驗證；Chunker 輸出依 [15](15_chunk_contract.md) 的六鍵 Schema、來源／任務／向量規則。資料形狀符合仍須檢查 Component 能力相容。
- Builder 將文件／CSV 轉成共同 JSON；是否提供暫存 URI、格式轉換範圍、存取與清理見 Q-016／Q-019。
- 剩餘待決：schema_id／profile 命名與版本、路由衝突的精確政策、輸入／解碼／下載大小與逾時、批次 envelope、回應／錯誤碼、ID／版本省略政策及正式 SDK。已確認的共同外層不重開。
- UI 遷移記 [UIB-011](10_ui_adjustment_backlog.md#uib-011-ingestion-parser-routing)；ParsedDocument／Chunk 預覽另見 UIB-012／013，本次不修改 Prototype。

