# Ingestion JSON Contract 與 Parser Input 草案

> 2026-10-29（Asia/Taipei）· 討論記錄／開發草案，尚未實作或凍結公開 API／SDK。
>
> 本文記錄使用者確認的 JSON-only、扁平輸入與多 Parser 自動路由方向，以及要求先保存的 Schema。它更新 05／07 舊 records／multipart 輸入設計；不凍結 ParsedDocument／Chunker 實際 Schema。ParserInput 的內部包裝仍是建議，待下一輪討論。

## 1. 已確認方向與責任

- Engine Runtime 的 Ingestion API 只接收 JSON body。RAG Builder 可提供文件／CSV 上傳及轉換；自行部署的呼叫端自行完成相同傳輸前處理，不要求部署 Builder。
- JSON 支援 inline 文字／物件、Base64 檔案與資源 URI。傳輸前處理不等於語意解析；原始 PDF 等內容仍由 Engine 的相容 Parser 處理。
- Payload 採扁平格式，不需要 source 或 mode；content／base64／uri 三選一。
- 接受未解析內容與上游已解析內容；後者由相容 Parser／Adapter 驗證及正規化，不強制重做解析。這不等於已核可直接匯入 Chunk／vectors。
- Parsing 可啟用多個 Parser，平台依能力自動路由；格式不重疊時不要求使用者配置 Router。同格式衝突才需預設策略或進階 parsing_profile。
- 沒有相容 Parser、路由歧義、格式與實際內容不符時明確報錯，不以載入順序選第一個，不默默改用其他 Parser。

## 2. 單筆文件 JSON Schema

機器可讀草案：[ingestion_document.schema.json](../schemas/ingestion_document.schema.json)。Schema 的單位是單筆文件，最小 request body 為：

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

content 可依已註冊 schema_id 傳入 fields／structure 等已解析內容，但具體識別、內容 schema 與 Adapter 尚待核定；此處不提供假定已凍結的結構範例。ID、版本與 metadata 由外層提供。若 Adapter 支援接收完整的外部文件物件，必須明定重複 ID／metadata 的一致性政策，不能靜默覆寫。

## 4. 是否也是 Parser 的 Input？

**是同一筆文件的資料來源，但不建議把 HTTP JSON 原封不動作為每個 Parser 的執行介面。** API contract 表達傳輸；Parser contract 表達已取得、可解析的內容。

| API 輸入 | Import／共用資源層 | Parser 收到的內容 |
|---|---|---|
| content 是文字 | 驗證、保留 | str |
| content 是 JSON object | 驗證外層、保留物件 | dict；再依選定 schema 驗證 |
| base64 | 檢查限制、嚴格解碼 | bytes 或受控可讀取資源 |
| uri | 授權取得、檢查限制 | bytes／受控資源，再依格式處理；不得把 URL 本身當文件文字 |

路由可先依宣告資訊選出候選，取得內容後再核對實際格式及 schema；取得、偵測與選定 Parser 的精確順序仍待實作設計。URL 指向 JSON 時，要依支援的格式正規化為物件或由對應 Adapter 解碼，不能假設所有 URL 都代表 PDF。

以下是 ParserInput 的 Python 形狀示意，不是已發布的 SDK：

```python
parser_input = {
    "document_id": "report-001",
    "source_revision": "v1",
    "media_type": "application/pdf",
    "schema_id": None,
    "content": b"...PDF bytes...",
    "metadata": {"department": "engineering"},
    "source_info": {
        "uri": "https://storage.example.com/report.pdf"
    },
}
```

這裡的 None 是內部草案的未指定表示，不是放寬 HTTP Schema 接受 null。parsing_profile 由 Router 解析為核可實例，不需要每個 Parser 再路由。Config、Secret 與可信執行資訊另外注入；使用者 metadata 不能覆蓋可信權限／來源。

| 持續傳遞資訊 | 原則 |
|---|---|
| document_id／source_revision | 取得／解碼不能任意改變文件身分；省略版本政策另議 |
| metadata | 保留已驗證業務資訊，遵守平台保留名稱 |
| 來源資訊 | 保留可追溯引用；精確欄位、保存期與敏感資訊遮罩待決 |
| 解析結果 | Parser 產生 ParsedDocument，而不是直接生成向量或任意 Chunk |

大型內容的 bytes／stream／resource handle、來源物件名稱、async／batch 簽名與資源釋放都仍屬 Q-002／Q-016／Q-017；不要求各 Parser 自行下載 URI 或實作 Base64 處理。

## 5. Parser 能力與 Chunker 相容

Parser 宣告可接受的 media_type、schema 及必要資源；多個 Parser 的啟用不代表每筆都執行全部，也不保證混合模態的聯合理解。相同格式只有一個可用實例時自動選用；有重疊時需明確預設／profile。格式副檔名僅為提示，不取代實際驗證。

ParsedDocument 使用共同外層格式，但每種 Chunker 仍有內容／結構需求。Parser 與 Chunker 依 produces／requires 能力及版本配對，不依特定實作名稱綁死；標題、頁面、表格與自訂結構的具體 schema 仍見 [Q-002 待討論清單](08_implementation_plan.md#parsed-document-schema-pending)。不相容時明確報錯；不默默攤平成文字。

## 6. 舊設計與待決事項

- 取代舊 API records[].fields 及 Engine multipart 的目標設計；不是新增永久相容別名。現有 Prototype／舊 YAML／圖面仍是歷史展示，沒有在本輪遷移。
- Builder 文件／CSV 入口轉成這份 JSON，再使用相同 Engine Pipeline。Builder 是否提供暫存資源 URI、哪些格式在 Builder 先轉換、存取授權與清理策略待 Q-016／Q-019。
- 舊 SourceAsset 是內部草案；ParserInput 可作它的後續具體化方向，正式類別／資源句柄尚未定案。
- 未決：ParsedDocument 實際結構、schema_id／profile 命名與版本、路由優先規則、輸入大小及逾時、批次包裝、回應／錯誤碼、舊資料遷移。已確認輸入方向不因此退回未定。
- API 外層及 Parser 專屬 schema 分開；支援任意 JSON object 不表示任意內容或 Chunk／vectors 都可直接入庫。
- UI 所需調整只登錄 [UIB-011](10_ui_adjustment_backlog.md#uib-011-ingestion-parser-routing)，本輪不改 Prototype。
