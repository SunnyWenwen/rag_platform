# ParsedDocument 0.1 草案與 Docling／MinerU 對照驗證

> 2026-10-30（Asia/Taipei）· D-46：依討論產出可驗證草案及實際映射案例；尚未凍結正式 SDK／API，不表示 Parser、Chunker 或部署能力已實作。

> 2026-10-31 文件同步：輸入為 [13 IngestionDocument](13_ingestion_parser_input_contract.md)，本文件定義 Parser 輸出／Chunker 輸入，切分後使用 [15 Chunk](15_chunk_contract.md)。三份 JSON Schema 各自單一維護，正式 SDK 版本凍結仍由 Q-002 追蹤。

## 0. 情境整理與分類總覽（報告摘要）

**這份文件整理的是「不同來源解析後，要用什麼共同格式保留內容與結構，交給後續 Chunker」**。設計保留簡單文字路徑，也允許頁面、段落、表格等結構；先定義資料如何表達與驗證，再由各 Component 分階段實作處理能力。

### 0.1 從哪些資料情境整理而來

| 資料情境 | 需要保留的資訊 | 分類／表示方向 |
|---|---|---|
| 純文字或簡單紀錄 | 原文、標題、已有摘要與業務 metadata | fields 保留內容，structure 可為 {} |
| 已有全文與標註位置 | 段落、標題、頁面範圍或上游切分點 | 全文＋範圍標註，即 text-spans |
| 上游已按頁／元素整理 | 每頁中的標題、段落、Block 內容及閱讀順序 | Page／Block 物件，即 page-blocks；全文依明確規則衍生 |
| 章節與跨頁內容 | 歸屬關係、來源頁面、跨頁延續 | 可選 parent_id／continuation_of 與多個 locations；頁面不預設為切分邊界 |
| 表格與 Excel | 欄列結構、搜尋用文字、sheet／儲存格來源 | 表格內容與文字表示分開保留；sheet 不冒充 PDF 頁碼，複雜內部格式可用註冊擴充 |
| 圖片與混合模態 | 原始資源引用、位置，以及可取得的 OCR／caption | 圖片 Block 關聯資源；沒有原圖時明確保留缺失狀態，不假設文字 Chunker 可處理 |
| PPTX | 投影片、元素及其結構／位置 | 以 slide 位置表示，按可保留資訊選擇共用或專屬結構 |
| Markdown 標題 | 文字內 #／## 等語法所表達的層級 | 建議 Parser 產生共用 heading Blocks；直接處理 Markdown 的 Chunker 另宣告能力 |
| Docling／MinerU 等工具輸出 | 原生閱讀順序、元素、來源與特殊資訊 | 透過版本明確的 Adapter 映射；核心能表達者正規化，特殊資訊明確擴充 |

### 0.2 分類結果：固定外層，結構按類型擴充

所有情境共用五個頂層 key：document_id／source_revision／fields／metadata／structure。內容放 fields，結構按對應欄位放 structure，例如 structure.text 對應 fields.text。

| 分類 | 直觀說明 | 內容基準 | 後續處理方向 |
|---|---|---|---|
| **無額外結構** | 有文字，未另外標註段落等資訊 | fields 的內容 | 相容的一般文字 Chunker |
| **全文＋範圍標註（text-spans）** | 原文存一份，Block 用 start／end 指出標題或段落在哪裡 | fields 完整字串 | 支援標註結構的 Chunker；一般文字使用須遵守必要約束 |
| **Page／Block（page-blocks）** | 內容先整理成多頁、多個元素物件 | Block.text，完整文字為衍生值 | 相容的結構型 Chunker |
| **已註冊的自訂結構** | 特殊需求有明確類型／版本與驗證規格 | 由該規格定義 | 支援該規格的 Chunker／Adapter，未註冊則拒絕 |

text-spans 與 page-blocks 是可並存的表示方式，不要求所有資料統一成其中一種；同一內容欄位採明確的一份結構規格。無 structure 不等於文字中沒有 Markdown 等內含語法，因此相容性還要考慮格式與能力。

<!-- classification-examples:parsed:start -->

以下先列四種分類，再附一份從 Docling 官方輸出映射而來的精簡例子；都使用 ParsedDocument 的五個頂層 key。它們是 Parser 的輸出／Chunker 的輸入，與 13 的 IngestionDocument 分屬不同階段。前三種分類由 §1 的共用 JSON 範例產生報告用精簡視圖，只省略可選資訊；自訂例子的資料與示意註冊 Schema 見 [report_cases.json](../examples/contracts/report_cases.json)。

#### 0.2.1 無額外結構：只有可處理的文字欄位

原文與標題在 fields，structure 為空；一般文字 Chunker 可以依 Token 或分隔規則處理選定文字欄位。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {"text": "清潔前先斷電。", "title": "設備手冊"},
  "metadata": {"department": "engineering"},
  "structure": {}
}
```

#### 0.2.2 text-spans：全文加上標題／段落範圍

fields.text 是基準；[0,4) 是標題、[5,12) 是段落，Block 不重複保存文字。完整範例另有頁碼與切分點，此處省略可選資訊。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {"text": "保養規範\n清潔前先斷電。"},
  "metadata": {},
  "structure": {
    "text": {
      "schema_id": "text-spans/0.1-draft",
      "blocks": [
        {"block_id": "b1", "type": "heading", "start": 0, "end": 4, "level": 1},
        {"block_id": "b2", "type": "paragraph", "start": 5, "end": 12, "parent_id": "b1"}
      ]
    }
  }
}
```

#### 0.2.3 page-blocks：按頁保存 Block 物件

Block.text 是基準；例子有兩頁。fields.text 是以兩個換行串接的衍生值，Chunker 仍可依設定跨頁合併，頁面不是強制切分邊界。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {"text": "保養規範\n\n清潔前先斷電。"},
  "metadata": {},
  "structure": {
    "text": {
      "schema_id": "page-blocks/0.1-draft",
      "pages": [
        {"page_number": 1, "blocks": [{"block_id": "b1", "type": "heading", "text": "保養規範", "level": 1}]},
        {
          "page_number": 2,
          "blocks": [{"block_id": "b2", "type": "paragraph", "text": "清潔前先斷電。", "parent_id": "b1"}]
        }
      ]
    }
  }
}
```

#### 0.2.4 已註冊自訂結構：企業自己的章節分類

company.custom/1 是示意客製規格，payload 記錄企業的章節分類；產生／驗證本例時，工具明確註冊了要求 section 為字串的 Schema。未註冊時會拒絕，且需要相容 Component，不表示平台預設支援此名稱。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {"text": "清潔前先斷電。", "title": "設備手冊"},
  "metadata": {"department": "engineering"},
  "structure": {"text": {"schema_id": "company.custom/1", "payload": {"section": "設備保養"}}}
}
```

#### 0.2.5 Docling 實際映射：標題、段落與來源頁碼

這是官方 multi_page 測資經既有參考 Adapter 轉換後，取前兩個 Block 的報告視圖；來源與雜湊見 §5。全文取至第二個 Block 結尾，省略其他內容、bbox 與原生擴充，metadata 明示為摘錄。這是轉成既有 text-spans 的例子，沒有建立自訂結構。Docling 第二個元素的局部 charspan 原為 [0,117)，重組全文後對應 [37,154)，因此不能把原生局部位置直接照搬。完整可驗證 JSON 見 [docling_report_excerpt.json](../examples/parsed_document/docling_report_excerpt.json)。

```json
{
  "document_id": "docling-multi_page",
  "source_revision": "e90f3440e9091b51a9c7fb0b138003933d71f540f24f4d04c05aa58fe3eb747a",
  "fields": {
    "text": "The Evolution of the Word Processor\n\nThe concept of the word processor predates modern computers and has evolved through several technological milestones."
  },
  "metadata": {"_rag": {"provider": "docling", "preview": true}},
  "structure": {
    "text": {
      "schema_id": "text-spans/0.1-draft",
      "blocks": [
        {
          "block_id": "b0000",
          "type": "heading",
          "locations": [{"kind": "page", "page_number": 1}],
          "level": 1,
          "start": 0,
          "end": 35
        },
        {
          "block_id": "b0001",
          "type": "paragraph",
          "locations": [{"kind": "page", "page_number": 1}],
          "start": 37,
          "end": 154
        }
      ]
    }
  }
}
```

四種表示的共同外層不變，差異集中在 structure 與內容基準；本輪未更改 Schema，也未新增 Parser／Chunker 執行能力。

<!-- classification-examples:parsed:end -->

### 0.3 Parser／Chunker 的分工與能力分類

Parser 負責產生內容與文件結構；Block／Element 是標題、段落、表格等文件單位。Chunker 再依 Token、策略與約束產生檢索單位：數個 Block 可合為一個 Chunk，過長 Block 也可再切。頁面、Block 與 Chunk 分開定義。

Parser 宣告「能產生什麼」，Chunker 宣告「接受什麼」。相同結構可由不同 Parser 產生，也可由不同策略的 Chunker 處理；配對依 Contract／版本／能力，不綁定特定實作名稱。Chunking 可固定一個 Component，或在多種輸入情境下依選定欄位的結構／格式自動派送；重疊時指定預設策略，每個切分任務預設只使用一個 Chunker。

| 能力層次 | 代表的結果 |
|---|---|
| **能表達／保存** | Schema 有位置保留內容、結構或具名擴充 |
| **能驗證／映射** | 符合形狀與語意，參考 Adapter 可轉換並檢查資訊保留 |
| **能實際執行** | 已有相容 Parser／Chunker，且資源、服務與必要約束都可滿足 |

三個層次分開驗收。不能因 Schema 支援某種結構，就宣稱對應的 OCR、表格切分、多模態或路由能力已交付。

### 0.4 現有驗證結果與後續重點

本節原有數字對應 Docling／MinerU；另新增 MarkItDown／PyMuPDF4LLM 真實解析驗證：7 次成功解析、14 份映射通過，模式與限制見 §5.1。§0.2.5 另附 Docling 官方映射的報告摘錄。

本次用 5 份 Docling＋1 份 MinerU 官方既有輸出，共 145 個元素進行映射與驗證；皆可形成 text-spans，其中 3 份也可轉成 page-blocks。原生 JSON 可以重建，驗證的是輸出資料的映射與保留，不是重新執行解析模型或 Chunker。

實測發現 19 個群組／公式等元素需要具名擴充、圖片測資缺原圖，以及部分群組、sheet／slide 不能直接套進按實體頁分組的形式。這些結果用來界定草案的支援範圍，後續再核定共用表格／圖片／特殊結構、正式供應者版本與實際 Chunker 能力。詳細證據與重現方式見 §5～6；本稿仍為 0.1 草案，UI／Engine 未因文件完成而實作。

## 1. 範圍與檔案

本文是 ParsedDocument 細節草案的權威位置；05 保留共用資料總覽，04 記錄 Module I/O，13 定義 API／Parser 共用輸入。IngestionDocument 與 ParsedDocument 是不同處理階段，不能直接互換。

| 檔案 | 用途 |
|---|---|
| [parsed_document.schema.json](../schemas/parsed_document.schema.json) | JSON Schema Draft 2020-12，五個固定外層、結構子 Schema、Block 與來源位置 |
| [plain_text.json](../examples/parsed_document/plain_text.json) | 最小文字文件 |
| [text_spans.json](../examples/parsed_document/text_spans.json) | 全文、標題、頁面、範圍與切分點 |
| [page_blocks.json](../examples/parsed_document/page_blocks.json) | 按頁分組的 Block 與衍生全文 |
| [validate.py](../examples/parsed_document/validate.py) | 跨欄位語意驗證的參考工具，不是正式 Engine SDK |
| [provider_adapters.py](../examples/parsed_document/provider_adapters.py) | 針對固定官方測資的轉換示範，不是生產 Parser／通用轉換器 |
| [provider_cases.json](../examples/parsed_document/provider_cases.json) | 上游固定 revision、路徑、URL 與 SHA-256 |
| [conformance_report.json](../examples/parsed_document/conformance_report.json) | 實際映射／保留檢查結果，不包含上游文件全文 |

正式 SDK 預計由 Python 共用模型產生 JSON Schema；目前先將 JSON Schema 保存為可審查草案，不建立另一份手寫的正式 Python 資料模型。

## 2. 共同外層

恰有五個必要頂層 key，不接受未宣告 key／null 容器：

| Key | 型別 | 草案語意 |
|---|---|---|
| document_id | 非空 string | 穩定文件識別；一來源派生多文件的 ID 規則另議 |
| source_revision | 非空 string | 來源內容版本；API 可省略，但 Parsing 輸出時須由平台既定政策解析完成。生成／更新政策尚未核定，不用 Parser 版本代替 |
| fields | 非空 object | 內容欄位，值為 JSON；另受 System／Parser output schema 約束，不預設所有值都可 Embedding／Indexing |
| metadata | object | 業務及受控追溯資訊；可為 {}，可信保留區不能由呼叫者覆寫 |
| structure | object | key 對應 fields 的欄位名稱；無結構時 {} |

結構欄位必須存在於 fields。內建 text-spans／page-blocks 對應欄位必須是 string；客製非文字結構由註冊規格定義。不要求所有文件都有 fields.text；它是一般文字流程的預設名稱。

本輪的頁面／表格／圖片資訊是資料表達與驗證範圍，不表示一般文字 Chunker 已支援所有內容。資料可保存、符合 Schema、具備下游可用能力是三個不同狀態。

## 3. 結構規格與內容基準

| 規格 | 內容基準 | 必要結構 |
|---|---|---|
| 無結構 | fields 的內容 | structure={} |
| text-spans/0.1-draft | 對應 fields 完整字串 | blocks；文字 Block 引用 start／end |
| page-blocks/0.1-draft | 按頁／閱讀順序排列的 Block.text | pages，每頁 page_number＋blocks；fields 對應字串為衍生值 |
| 已註冊自訂 schema_id | 由註冊規格定義 | schema_id＋payload，另需明確註冊的 Schema／語意驗證 |

### 3.1 全文與位置

文字位置採 Unicode code point、0-based、半開區間 [start,end)，以此版本 ParsedDocument 的對應 fields 字串為準。不能把上游元素內 charspan、UTF-8 byte offset、JavaScript UTF-16 index 或原始 PDF 字元索引直接照搬。

文字 Block 的範圍須非空、合法且依閱讀順序排列；允許不同結構用途的範圍重疊，不要求 headings 的文字範圍包含其子段落。非文字 Block 可沒有文字範圍，不應為圖片捏造 OCR 文字。原文修改後必須重算位置及受影響切分點。

text-spans 的 pages 是可選文字範圍表，不是所有來源都必須產生。若只有 Block 的來源頁碼／座標，放 locations 即可，不猜測整頁的連續文字範圍。原始空白頁可在來源描述保存，頁碼可有間隔。

### 3.2 Page／Block 內容

每頁編號為正整數且遞增、不重複，可保留空白頁。各頁陣列與 Block 陣列共同決定閱讀順序；Block ID 在同一欄位結構內唯一，父子／延續引用可跨頁。

本稿固定衍生全文規則：依頁面與 Block 順序，取非空 Block.text，以兩個 LF（即 \\n\\n）串接。空白頁、沒有文字的圖像／群組不加入假文字，也不靠串接符推測來源頁碼。fields 對應字串必須等於此結果；參考工具會檢查，正式串接策略如需變更須改結構版本。

頁面是來源資訊，不是強制切分邊界。若一個邏輯元素跨頁，可以在 text-spans 使用多個 locations；按頁輸入可保留片段、使用 continuation_of 指向先前片段。不能一方面合併文字，一方面丟掉片段來源。

Page／Block 的 pages 主要用於實體頁面；Excel sheet、PPTX slide 不自動冒充 PDF page。這些來源可使用通用 Block 的 sheet／slide locations 與 text-spans，或後續註冊的專屬結構。

### 3.3 Block 與關係

核心類型：heading、paragraph、list_item、table、image、code。block_id 必填；parent_id、continuation_of 可選，引用須存在、不得循環；continuation_of 必須指向閱讀順序較早的 Block。heading.level 為可選正整數，沒有可靠資訊時不猜測層級。

paragraph 可明確標註 role=body／header／footer／caption／note／aside，保留用途差異；不能將所有非正文都當成一般段落。父子表示文件結構歸屬，不要求父 Block 的文字範圍涵蓋子 Block。

**實際測資揭露的擴充缺口**：Docling 另有 group、sheet 容器與 formula，六種核心類型無法完整涵蓋。本稿加入 extension 作為明確擴充鉤子：必須帶 extension_type 與 data_ref，且由明確註冊的 payload Schema 驗證。extension 不是通用語意，不表示一般 Chunker 理解公式或群組。未知類型不能直接假裝成 paragraph。

參考 Docling 映射把群組／公式原生物件保留為 source.docling-item/1.10.0；這個註冊只檢查來源識別與基本形狀，屬原生保留，不代表已建立可攜公式／群組規格。完整原生 Schema 驗證及標準化語意仍需正式 Adapter 配套。

### 3.4 表格、圖片與來源位置

- table／image 透過 data_ref 引用同一份文件 fields 中的內容或資源描述；不能引用不存在的鍵。表格可另有文字表示供搜尋，但文字呈現與結構資料須明確區別。
- 本輪保留 Docling 原生 table data；其儲存格／合併欄列資訊能保存及重建，但尚未標準化成跨 Parser 共用的表格子 Schema。文字呈現的 Token、重複表頭與切分策略屬後續 Component 能力。
- image 若只有位置／原生 item reference，可標示資源不可取得；不能用檔名或 reference 假稱已有原圖。未取得資源的文件不能當作已驗證多模態可執行。
- locations 是陣列，支援 page、slide、sheet、element。PDF 頁碼、Slide 編號從 1 起；sheet 使用名稱與可選 cell_range，不混用物理頁碼。
- bbox 明示 left／top／right／bottom、origin、unit，選填 width／height。原點可 top-left／bottom-left，單位可 pt／px／emu／normalized／source。source 表示未經本 Adapter 正規化的來源單位，需對應來源規格解讀，不能直接用於跨工具幾何運算。
- Docling 的元素內 charspan 及原生幾何資料保留在具名 extensions；全文 offset 由轉換後內容重算。參考 PPTX 使用 EMU；Excel 來源的格狀 bbox 保留在原生資訊，不錯標為 PDF points。

參考映射會產生 table_*／image_*／native_* 欄位供示範；正式 Component 必須宣告其輸出欄位／命名空間及可用能力，並對接 System Schema。這些示範名稱不是要求產品暴露所有原生資料給 Embedding／UI。

### 3.5 切分點與相容性

text-spans 的 split_points 用 offset；page-blocks 用 before_block_id。kind 為 preferred／required；位置必須合法、不重複、有序，不能把文件開頭／結尾當額外切分點。

required 表示 Chunk 不得跨越該邊界，不表示區間內不可因 Token 上限再次切分。不可拆表格／其他原子單位屬另一個能力，尚未標準化。Chunker 若不支援必要約束，必須拒絕或要求明確選擇可用策略，不能忽略。

Parsing 可多選自動路由；Chunking 可固定一個 Component，或按選定切分欄位的結構／格式／能力路由。格式相容不代表策略唯一，同一種文字的 Fixed-size／Recursive 需有預設選擇。每個切分任務預設選一個 Chunker，不因多選就平行生成多套 Chunk。

Markdown 的標題是文字內含結構，structure={} 不代表沒有內含語法。首版建議 Parser 產生 heading Blocks；直接吃 Markdown 的 Chunker 可另宣告格式能力，但此稿沒有假稱已實作，也沒有額外發布第三個 Markdown 結構規格。

## 4. 驗證層次與自訂擴充

| 驗證層次 | 本輪工具檢查 |
|---|---|
| JSON Schema | 型別、必填、未知 key、結構分支、Block／位置的基本形狀 |
| 共同語意 | structure 與 fields 對應、offset 上下界、ID 唯一、引用及循環、衍生文字、bbox 方向、切分點 |
| 已註冊擴充 | 未註冊 schema_id／extension_type 拒絕；明確傳入的額外 Schema 才可用，不依識別下載程式／Schema |
| 執行能力 | 需由正式 Engine 驗證 Chunker 能力、資源、Tokenizer／服務；本輪未實作 |

Schema 檔案為共用核心與內建 $defs；RegisteredStructure 只定義擴充 envelope，**不能單靠通過這個分支就視為已支援自訂內容**。參考語意工具要求註冊 Schema，拒絕外部 $ref 下載；客製跨欄位語意驗證仍需 Developer 配套。

metadata／fields 為 JSON 資料，仍需 System Schema 及可信權限政策；公共 Schema 不是 ACL 驗證。參考 adapter 的 metadata._rag 是受控追溯區候選，正式名稱／隱私與保留政策留 Q-006／Q-016；呼叫端不得以輸入內容偽造。

## 5. 官方測資：轉成既有結構的實際驗證結果

來源固定於 Docling repo revision af2dbadb4cd3fa39786916157a5c174eeb9bb7bf 與 MinerU revision 14db546c732e9829c949dbaefd9f1459c3da55a7，逐檔 SHA-256 見 provider_cases.json。Docling 測資原生格式為 DoclingDocument 1.10.0；MinerU 正例為 docvortex.middle／2.0、producer 4.0.12 的既有輸出。日期僅記錄本次驗證，不宣稱已覆蓋所有版本。

**實際執行的是官方既有輸出 JSON 的轉換與驗證**，沒有執行 Docling／MinerU 模型、OCR、原始檔解析、圖片下載、Chunker 或檢索。上游原生測資不複製到此 repo，重跑時從固定 URL 取得並核對雜湊。

本節的兩欄是**轉換目標**，不是「可否自訂新結構」的判定：

- **text-spans 通過**：原生輸出經參考 Adapter 轉成已定義的 text-spans/0.1-draft，通過共同形狀、位置及引用等檢查；沒有因此建立新的 structure.schema_id。表中的 19 個 extension 是 Block 層級的原生資料保留，外層仍使用既有 text-spans；它與另註冊一種自訂 Structure 是不同層次。
- **page-blocks 未能轉換**：這份測資無法由目前的參考 Adapter 在保留原意的前提下轉成 page-blocks，例如群組沒有唯一頁碼、來源是 sheet／slide，不能直接改標成物理 page。這不是宣稱 page-blocks 整體不支援該 Parser，也不只是 JSON Schema 驗證失敗；其餘三份案例確實可以轉換。
- **自訂結構**：屬另一條擴充路徑，必須明確定義 schema_id、註冊 Schema／必要語意驗證，並具備相容 Chunker。官方表格中的通過數不等於已註冊自訂結構數。

| 官方案例 | 來源元素數 | 轉成既有 text-spans | 轉成既有 page-blocks | 限制／觀察 |
|---|---:|---|---|---|
| Docling multi_page | 61 | 映射／驗證通過 | 目前參考 Adapter 無法無損轉換 | 8 個群組沒有唯一頁面，不能猜頁碼或重排閱讀順序 |
| Docling picture_classification | 11 | 映射／驗證通過 | 映射／驗證通過 | 有 2 個圖片元素，但測資沒有原圖，不能驗證原圖可用 |
| Docling code_and_formula | 16 | 映射／驗證通過 | 映射／驗證通過 | 公式以 1 個已註冊原生 extension 保存，尚非通用公式語意 |
| Docling xlsx_05_table_with_title | 3 | 映射／驗證通過 | 目前參考 Adapter 無法無損轉換 | 2 個表格與 sheet 容器，使用 sheet 位置，表格 payload 仍是原生格式 |
| Docling powerpoint_sample | 37 | 映射／驗證通過 | 目前參考 Adapter 無法無損轉換 | 使用 slide 位置；9 個群組／容器以原生 extension 保存 |
| MinerU before_middle | 17 | 映射／驗證通過 | 映射／驗證通過 | 頁碼 0→1；保留文字、標題、header／aside 與原生 bbox；未涵蓋 MinerU 表格／圖片案例 |
| MinerU model_image_reference 測試資料容器 | — | 如預期拒絕 | — | 不是 MiddleJson，不把任意 JSON 當成可解析的原生文件 |

六個正例共 145 個元素逐項映射，檢查無靜默漏項、文字與表格 payload 保留；利用具名 extensions／追溯資訊重建的**原生 JSON 與輸入相等**。共有 19 個 extension 元素，屬原生保留；不能把 JSON 可重建解讀為全部語意可攜、原始檔／圖片二進位可重建或下游 Chunker 已相容。

page-blocks 有三個正例通過。其餘失敗是參考轉換器無法在保留原意的前提下完成分頁，不是用任意改頁碼讓它過 Schema；那些輸入仍可用 text-spans 保留來源，或後續增加專屬結構／Adapter。

### 5.1 MarkItDown／PyMuPDF4LLM：實際本地解析與 Contract 驗證

**結論：兩者都可經 Parser Component／Adapter 接入，目前 IngestionDocument 與 ParsedDocument Schema 不需修改。** 本節使用自行產生的數位 PDF／DOCX／HTML 進行真實解析，與 §5 前半使用 Docling／MinerU 官方既有輸出 JSON 的驗證方式分開統計。

| Parser／模式 | 實際輸出 | 映射到既有 Contract | 實測結果／邊界 |
|---|---|---|---|
| MarkItDown 0.1.9，PDF／DOCX／HTML | DocumentConverterResult：markdown、可選 title | Markdown 放 fields.text，structure={}；或以 Markdown 語法解析成 text-spans | 3 次解析、6 份映射通過；DOCX／HTML 的標題與 Markdown 表格可標註，本次 PDF 結果只有文字段落 |
| PyMuPDF4LLM／PyMuPDF 2.0，Legacy Markdown | 整份 Markdown 字串 | 無額外結構／text-spans | 1 次解析、2 份映射通過；保留完整輸出文字，整份字串不自動提供頁碼 |
| PyMuPDF 2.0，Legacy／Layout 的 page_chunks | 每頁 dictionary 清單，含頁面 metadata 與 text | page-blocks／text-spans；依原生資料保留 page、空白頁與可取得的 bbox | 2 次解析、4 份映射通過；兩種模式都保留第 3 頁空白頁，Layout 另有 page_boxes／pos |
| PyMuPDF 2.0，Layout JSON | pages／boxes、boxclass、文字行、表格及幾何 | text-spans／page-blocks，table payload 另存 fields，bbox 用 page locations | 1 次解析、2 份映射通過；本次涵蓋 heading／paragraph／table，原生表格資料保留 |

合計 **7 次成功解析、14 份 ParsedDocument 映射**，均通過 Schema 與共同語意檢查。另測 4 個無效／衝突頁面資料及未知 Layout class 的拒絕案例；Legacy 模式的 to_json 如預期回 NotImplementedError，需明確選 Layout 能力。實際版本、呼叫方式與逐案結果見 [lightweight_conformance_report.json](../examples/parsed_document/lightweight_conformance_report.json)。

#### 5.1.1 API／Parser 輸入如何接合

本地工具先以共同 IngestionDocument Schema 驗證 base64 請求，再嚴格解碼並核對原始 bytes。MarkItDown 實際使用 convert_stream(BytesIO, StreamInfo)；PyMuPDF 實際使用 pymupdf.open(stream=bytes, filetype="pdf")。這證明不需在 Engine 增加 multipart，也不需為每個 Parser 更換公共輸入外層；正式路由、資源 resolver、Component 註冊與 Config 仍由 Engine 實作。

#### 5.1.2 兩種輸出模式要明確區分

- MarkItDown 0.1.9 的實測結果只有 markdown／title，沒有 pages 屬性。參考 Adapter 依 CommonMark 語法辨識標題、段落、程式碼與表格，範圍指向**輸出的 Markdown 字串**。它不能從全文猜出原始頁碼／bbox；Markdown 中的表格／圖片引用也不等於已取得標準儲存格模型／原圖。
- PyMuPDF 的 page_chunks=True 是解析輸出的按頁組織方式，接入此平台時轉成 ParsedDocument 的頁面／Block 資訊；它不是平台最終 Chunk，也沒有因此略過 Chunking Module。
- 本次 2.0 的 Legacy 頁碼在 metadata.page，Layout 在 metadata.page_number。Adapter 核對原生欄位；兩者衝突或缺少頁面身分時拒絕，不用陣列索引猜測頁碼。Layout page_boxes 的 pos 對應每頁 Markdown；轉成全文範圍時要加上頁面串接偏移。
- Layout JSON 的 bbox 使用 top-left／pt，保留原生 page 尺寸。Markdown token 對到 page_boxes 時，bbox 代表原生元素範圍，並非每個字元的精確裁切範圍；沒有可靠對應的位置則只保留頁碼。
- **版本注意**：官方 PyMuPDF4LLM 2.0 套件已改為相容性 shim，功能由 PyMuPDF 2.0 提供。官方建議改用 Document.to_markdown／to_json／to_text；本次也驗證 Document 方法與 pymupdf4llm 相容入口輸出相等。不可把舊 1.x 的呼叫／欄位假設直接套到全部版本。

#### 5.1.3 相容性與解析品質分開驗收

本次 PDF 原始表格是 2 欄：MarkItDown 的 PDF Markdown 沒有保留表格結構，PyMuPDF Layout JSON 在此小樣本辨識成 1 欄。Adapter 保留各自的實際結果，沒有為了符合 Schema 修補或捏造原始欄列。這是上游解析品質觀察，不能因 Contract 驗證成功，就宣稱原始版面／內容完全正確或用此單例評比整體品質。

PDF 有兩頁文字、一頁空白頁，包含標題、段落、簡單表格與程式碼；所有 PyMuPDF 測試使用非 OCR 路徑或明確 use_ocr=False。未測掃描件、OCR、圖片資源、Office 延伸模式、所有 Markdown 巢狀／HTML 語法或真實企業語料。參考轉換器只覆蓋此次模式／類型；未知原生 class 明確拒絕，純 Markdown 仍保留全文，不能由未標註部分推論完整結構已識別。

參考 Adapter 的 metadata._rag.field_formats 是範例格式提示，正式欄位／信任與路由協定仍待核定；不是新增已凍結的公開頂層 key。Parser 的輸出能力、生成的 table_* 欄位與相容 Chunker 須正式宣告，表格標準化與結構型 Chunker 邏輯另外交付。

#### 5.1.4 重現方法與程式位置

```bash
python -m pip install -r examples/parsed_document/requirements_lightweight_parsers.txt
python examples/parsed_document/check_lightweight_parsers.py --work-dir /tmp/rag-parser-fixtures --report /tmp/rag-parser-report.json
```

[check_lightweight_parsers.py](../examples/parsed_document/check_lightweight_parsers.py) 產生自有測資並執行本地套件；[markdown_parser_adapters.py](../examples/parsed_document/markdown_parser_adapters.py) 提供示範映射；[requirements_lightweight_parsers.txt](../examples/parsed_document/requirements_lightweight_parsers.txt) 固定本次直接依賴版本。二進位測資與完整映射結果寫到指定暫存目錄，不把外部套件或模型放入此 repo。這不是正式 Engine／Runtime／Chunker 整合測試，也沒有修改 UI。

## 6. 重現方法

在 repo 根目錄執行，建議使用獨立 Python 環境：

```bash
python -m pip install -r examples/parsed_document/requirements.txt
python examples/parsed_document/test_contract.py
python examples/parsed_document/check_provider_samples.py --cache-dir /tmp/pd-fixtures --output-dir /tmp/pd-normalized --report /tmp/pd-report.json
```

本輪共同契約案例為 7 個正例／29 個反例，包含 Unicode、未知欄位、重複 ID、錯誤 offset、循環／懸空關係、錯誤衍生全文、未知擴充及外部 Schema 引用。官方映射另有 6 正例／1 預期拒絕；不將它們稱作 Parser／Engine 整合測試。

## 7. 審閱與後續取捨

1. 本稿已將兩種結構、明確基準、六種核心類型＋extension、關係／位置／邊界語意具體化，供逐項核定；尚未凍結 SDK。
2. 決定 group／formula 是否升為平台共用類型，或繼續透過具名擴充處理；不能為了六種類型上限丟掉原生資訊。
3. 決定是否新增 sheet／slide 分組結構；目前保留原生位置，不將所有來源都強制分頁。
4. 補上更多 MinerU 表格／圖片／跨頁延續及不同版本的真實輸出，與可取得的二進位資源；本次單一文字型 MiddleJson 正例不代表所有 MinerU 模態已驗證。
5. 正式核定表格／圖片子 Schema、資源生命週期、解析與來源版本、可信 metadata、客製註冊／相容遷移及 Markdown 格式宣告位置。
6. Chunker 的能力與路由另外實作；對應 UI 只記錄 [UIB-012](10_ui_adjustment_backlog.md#uib-012-parsed-document-structures)，不修改 Prototype。

## 8. 官方參考

- [Docling 文件模型](https://docling-project.github.io/docling/concepts/docling_document/)
- [Docling 官方測資目錄](https://github.com/docling-project/docling/tree/af2dbadb4cd3fa39786916157a5c174eeb9bb7bf/tests/data)
- [MinerU 輸出格式與不同入口](https://opendatalab.github.io/MinerU/reference/output_files/)
- [MarkItDown 官方結果物件（固定原始碼 revision）](https://github.com/microsoft/markitdown/blob/7482c092d9c0074a89803c9fdb63a969e7fe17fc/packages/markitdown/src/markitdown/_base_converter.py)
- [PyMuPDF4LLM 官方 API 與 2.0 遷移](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html)
- [PyMuPDF4LLM 2.0 shim 說明（固定原始碼 revision）](https://github.com/pymupdf/pymupdf4llm/blob/38e2d1da51d0f198cda2aaa161f21f75074bcced/README.md)
- [MinerU 官方 MiddleJson fixture](https://github.com/opendatalab/MinerU/blob/14db546c732e9829c949dbaefd9f1459c3da55a7/tests/fixtures/pdf_text_5635_5636/before_middle.json)

外部格式與套件會演進；本文件的相容結論以固定來源與本次報告為界，不以目前網頁內容自動更新或自動承諾相容。
