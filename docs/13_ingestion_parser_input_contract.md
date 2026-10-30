# Ingestion API／Parser 共用輸入 Contract

> 2026-10-29（Asia/Taipei）· 共用輸入 Schema 與語意已確認（D-44／D-45）；尚未實作 API／SDK，批次、版本政策及執行細節另議。
>
> 本文記錄 JSON-only、扁平輸入、多 Parser 自動路由，以及使用者確認「Ingestion API 與 Parser Input 使用相同 Schema」。共同物件稱 IngestionDocument；不另設另一份公開 ParserInput。它更新 05／07 舊 records／multipart 及先前 ParserInput 轉換設計；ParsedDocument／Chunker 實際 Schema 仍待討論。

## 0. 情境整理與分類總覽（報告摘要）

**這份文件整理的是「各種來源的資料，如何透過同一個入口交給 RAG Engine」**。使用者可以送簡單文字、結構化紀錄、原始文件，或已被其他工具解析好的內容；平台統一接收 JSON，由相容 Parser 處理，不要求所有呼叫端先完成同樣程度的解析。

### 0.1 從哪些使用情境整理而來

| 使用情境 | 輸入方式與例子 | 誰負責處理 |
|---|---|---|
| 直接送一段文字 | content 是文字，例如操作說明 | 相容文字 Parser 驗證並產生 ParsedDocument |
| 一筆資料有多個內容欄位 | content 是 JSON object，包含原文、標題、已有摘要等；不是多筆文件 | 相容 records Parser／Adapter 轉成內容欄位，後續模組另選欄位用途 |
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

#### 0.2.5 content：上游已經解析並保留結構

原文與 heading／paragraph 範圍已整理好，由相容 Adapter 驗證與組成 ParsedDocument。外層 schema_id 是「輸入內容形狀」的示意識別，須註冊對應 Adapter；內層 schema_id 是文字結構規格。API body 使用 IngestionDocument，Adapter 以 content 中的 fields／structure 組成 ParsedDocument。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "schema_id": "example.preparsed-content/0.1-draft",
  "content": {
    "fields": {"text": "保養規範\n清潔前先斷電。"},
    "structure": {
      "text": {
        "schema_id": "text-spans/0.1-draft",
        "blocks": [
          {"block_id": "b1", "type": "heading", "start": 0, "end": 4, "level": 1},
          {"block_id": "b2", "type": "paragraph", "start": 5, "end": 12, "parent_id": "b1"}
        ]
      }
    }
  },
  "metadata": {}
}
```

上述五例都符合共同外層；media_type／schema_id 能省略的條件仍依正文。對應的 Parser／服務能力必須另外具備，範例通過 Schema 不代表 Runtime 已實作。

<!-- classification-examples:ingestion:end -->

### 0.3 責任分工與目前範圍

| 層級 | 責任 |
|---|---|
| RAG Builder／自行部署的呼叫端 | 提供方便的上傳／映射／檔案傳輸轉換；組成 JSON |
| Engine 的共用入口／SDK 資源能力 | 驗證共同外層、授權取得內容、解碼及必要限制；路由到已設定的 Parser |
| Parser／Adapter | 理解來源或轉換已解析資料，產出統一 ParsedDocument，詳見 [14 的情境與結構分類](14_parsed_document_contract.md#0-情境整理與分類總覽報告摘要) |

JSON-only、扁平輸入、三種來源、API／Parser 共用契約與多 Parser 路由方向已確認；API／SDK 尚未實作，實際格式需有相容 Component 才可執行。單筆外層 Schema 已記錄；批次、限制、版本與正式供應者支援仍依正文逐項核定。直接匯入最終 Chunk／vectors 另外討論，不混入「上游已解析」的支援承諾。

## 1. 已確認方向與責任

- Engine Runtime 的 Ingestion API 只接收 JSON body。RAG Builder 可提供文件／CSV 上傳及轉換；自行部署的呼叫端自行完成相同傳輸前處理，不要求部署 Builder。
- JSON 支援 inline 文字／物件、Base64 檔案與資源 URI。傳輸前處理不等於語意解析；原始 PDF 等內容仍由 Engine 的相容 Parser 處理。
- Payload 採扁平格式，不需要 source 或 mode；content／base64／uri 三選一。
- **API 單筆文件與 Parser Input 共用 IngestionDocument 及同一份 JSON Schema**；Parser 可接收經共同驗證／反序列化的 SDK 物件，但欄位、型別與驗證規則一致，不維護第二份轉換後的輸入 contract。
- 接受未解析內容與上游已解析內容；後者由相容 Parser／Adapter 驗證及正規化，不強制重做解析。這不等於已核可直接匯入 Chunk／vectors。
- Parsing 可啟用多個 Parser，平台依能力自動路由；格式不重疊時不要求使用者配置 Router。同格式衝突才需預設策略或進階 parsing_profile。
- 沒有相容 Parser、路由歧義、格式與實際內容不符時明確報錯，不以載入順序選第一個，不默默改用其他 Parser。

## 2. 單筆文件 JSON Schema

機器可讀共同定義：[ingestion_document.schema.json](../schemas/ingestion_document.schema.json)。它是 API 與 Parser Input 的同一份外層 Schema；單位是單筆文件，不是整個批次或 HTTP 回應。最小 request body／Parser Input 為：

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

本文保存單筆 body 草案；批次 request 的容器、欄位名、是否與單筆共用 endpoint、逐筆錯誤及 partial 行為仍待 Q-019。既有 /v1/ingestions、202／run_id 是 API 基線，不以此單筆 Schema 宣稱整份 OpenAPI 已凍結。

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

預設 Structured records Parser 可依既定設定把 content 的鍵轉入 fields；正式預設／必要欄位與未知欄位政策仍由 Q-002 決定。Builder CSV 映射只做一次；若已映射成目標鍵，Parser 不重複映射。metadata 使用外層欄位，不從任意 content 欄位自動猜測。

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

content 可依已註冊 schema_id 傳入 fields／structure 等已解析內容。2026-10-30 已新增 [ParsedDocument 0.1 輸出草案與參考映射](14_parsed_document_contract.md)，但 API 的原生 content 格式識別與正式 Adapter 仍須核定，不能直接把 ParsedDocument Schema 當成共同 IngestionDocument；此處不提供假定已凍結的結構範例。ID、版本與 metadata 由外層提供。若 Adapter 支援接收完整的外部文件物件，必須明定重複 ID／metadata 的一致性政策，不能靜默覆寫。

## 4. 是否也是 Parser 的 Input？

**是，Ingestion API 與 Parser 的 Input 共用 IngestionDocument 及相同 Schema。** 原先另建「content 已轉成 bytes、另加 source_info」的 ParserInput 草案已由本決策取代，不再作為目標介面。

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

ParsedDocument 使用共同外層格式，但每種 Chunker 仍有內容／結構需求。Parser 與 Chunker 依 produces／requires 能力及版本配對，不依特定實作名稱綁死；標題、頁面、表格與自訂結構的具體 schema 現有 [14 的可驗證草案](14_parsed_document_contract.md)，剩餘取捨仍見 [Q-002 待討論清單](08_implementation_plan.md#parsed-document-schema-pending)。不相容時明確報錯；不默默攤平成文字。

## 6. 舊設計與待決事項

- 取代舊 API records[].fields 及 Engine multipart 的目標設計；不是新增永久相容別名。現有 Prototype／舊 YAML／圖面仍是歷史展示，沒有在本輪遷移。
- Builder 文件／CSV 入口轉成這份 JSON，再使用相同 Engine Pipeline。Builder 是否提供暫存資源 URI、哪些格式在 Builder 先轉換、存取授權與清理策略待 Q-016／Q-019。
- 舊 SourceAsset 及另設 ParserInput 是先前內部草案；公開 Parser 輸入統一用 IngestionDocument，不再轉換為另一份資料契約。內部資源管理可保留實作物件，不能要求 Developer 依賴它們或變更共同 schema。
- 未決：ParsedDocument 實際結構、schema_id／profile 命名與版本、路由優先規則、輸入大小及逾時、批次包裝、回應／錯誤碼、舊資料遷移。已確認輸入方向不因此退回未定。
- API／Parser 的共同外層是同一份 Schema；各 Component 對 content 的專屬內容限制另宣告，屬共同契約上的進一步驗證，不是第二份輸入 envelope。支援 JSON object 不表示任意內容或 Chunk／vectors 都可直接入庫。
- UI 所需調整只登錄 [UIB-011](10_ui_adjustment_backlog.md#uib-011-ingestion-parser-routing)，本輪不改 Prototype。
