# ParsedDocument 0.1 草案與 Docling／MinerU 對照驗證

> 2026-10-30（Asia/Taipei）· D-46：依討論產出可驗證草案及實際映射案例；尚未凍結正式 SDK／API，不表示 Parser、Chunker 或部署能力已實作。

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

## 5. 官方測資實際對照結果

來源固定於 Docling repo revision af2dbadb4cd3fa39786916157a5c174eeb9bb7bf 與 MinerU revision 14db546c732e9829c949dbaefd9f1459c3da55a7，逐檔 SHA-256 見 provider_cases.json。Docling 測資原生格式為 DoclingDocument 1.10.0；MinerU 正例為 docvortex.middle／2.0、producer 4.0.12 的既有輸出。日期僅記錄本次驗證，不宣稱已覆蓋所有版本。

**實際執行的是官方既有輸出 JSON 的轉換與驗證**，沒有執行 Docling／MinerU 模型、OCR、原始檔解析、圖片下載、Chunker 或檢索。上游原生測資不複製到此 repo，重跑時從固定 URL 取得並核對雜湊。

| 官方案例 | 來源元素數 | text-spans | page-blocks | 限制／觀察 |
|---|---:|---|---|---|
| Docling multi_page | 61 | 通過 | 參考轉換器明確拒絕 | 8 個群組沒有唯一頁面，不能猜頁碼或重排閱讀順序 |
| Docling picture_classification | 11 | 通過 | 通過 | 有 2 個圖片元素，但測資沒有原圖，不能驗證原圖可用 |
| Docling code_and_formula | 16 | 通過 | 通過 | 公式以 1 個已註冊原生 extension 保存，尚非通用公式語意 |
| Docling xlsx_05_table_with_title | 3 | 通過 | 參考轉換器明確拒絕 | 2 個表格與 sheet 容器，使用 sheet 位置，表格 payload 仍是原生格式 |
| Docling powerpoint_sample | 37 | 通過 | 參考轉換器明確拒絕 | 使用 slide 位置；9 個群組／容器以原生 extension 保存 |
| MinerU before_middle | 17 | 通過 | 通過 | 頁碼 0→1；保留文字、標題、header／aside 與原生 bbox；未涵蓋 MinerU 表格／圖片案例 |
| MinerU model_image_reference 測試資料容器 | — | 如預期拒絕 | — | 不是 MiddleJson，不把任意 JSON 當成可解析的原生文件 |

六個正例共 145 個元素逐項映射，檢查無靜默漏項、文字與表格 payload 保留；利用具名 extensions／追溯資訊重建的**原生 JSON 與輸入相等**。共有 19 個 extension 元素，屬原生保留；不能把 JSON 可重建解讀為全部語意可攜、原始檔／圖片二進位可重建或下游 Chunker 已相容。

page-blocks 有三個正例通過。其餘失敗是參考轉換器無法在保留原意的前提下完成分頁，不是用任意改頁碼讓它過 Schema；那些輸入仍可用 text-spans 保留來源，或後續增加專屬結構／Adapter。

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
- [MinerU 官方 MiddleJson fixture](https://github.com/opendatalab/MinerU/blob/14db546c732e9829c949dbaefd9f1459c3da55a7/tests/fixtures/pdf_text_5635_5636/before_middle.json)

外部格式與套件會演進；本文件的相容結論以固定來源與本次報告為界，不以目前網頁內容自動更新或自動承諾相容。
