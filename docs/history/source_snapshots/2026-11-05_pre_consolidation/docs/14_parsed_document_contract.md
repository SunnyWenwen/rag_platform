> 歷史來源快照：docs/14_parsed_document_contract.md；來源 commit 916734ac0bbe0631a205bfd52626ce332aa7beb2。2026-11-05 整合後不再作現行規格；相對連結固定到來源版本。現行入口：[README](https://github.com/SunnyWenwen/rag_platform/blob/docs/rag-system-factory/README.md)。

# 14 — ParsedDocument：Parser／Chunker 共用契約

更新：2026-11-02。現行草案為 **0.2-draft**；採用已確認的平面 `units` 設計，取代 0.1 的 `fields`＋`structure`。正式 SDK／版本發布仍由 M0 凍結。

## 0. 情境與分類結果（報告摘要）

所有 Parser 都產出同一種 ParsedDocument；不同來源只影響 Parser 的整理策略，不增加 Chunker 輸入結構種類。

| 來源情境 | Parser 整理方式 | Chunker 接到的內容 |
|---|---|---|
| 純文字／多欄位 JSON／CSV 列 | 文字或紀錄整理成一個 Unit | 一筆 dict，預設 text，其他為可複製欄位 |
| PDF／PPT／Excel、已有 page／span／block | Parser 決定閱讀順序、段落／章節／頁面邊界，展平成 Units | 有序的獨立 Unit；page／slide／sheet 是來源欄位，不是結構路由 |
| 表格 | 逐列補上表頭語意，或整表轉 Markdown | 每列一個 Unit，或整表一個 Unit |
| 圖片／流程圖 | 具備能力的 Parser 產生 OCR／描述，可附來源 URI | 描述放 text；Chunker 不解讀圖片 |
| 上游已解析資料 | Adapter 驗證／正規化成 Units | 與原始資料解析後完全相同的契約 |

### 0.1 分類範例

<!-- classification-examples:parsed:start -->

所有例子共用四個頂層鍵；分類代表來源情境，不是不同結構型別。

#### 0.1.1 純文字／紀錄：一個 Unit

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "units": [{"text": "清潔前先斷電。", "title": "設備手冊"}],
  "metadata": {"filename": "manual.pdf"}
}
```

#### 0.1.2 多頁／章節：獨立 Units，保留 Markdown 標題

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

#### 0.1.3 表格：逐列補齊語意

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "warranty",
  "source_revision": "v1",
  "units": [{"text": "產品 A 的保固為 1 年。", "product": "A"}, {"text": "產品 B 的保固為 2 年。", "product": "B"}],
  "metadata": {"filename": "manual.pdf"}
}
```

#### 0.1.4 圖片：描述文字與來源 URI

資料形狀範例；不代表已執行正式 Parser 或 Chunker。

```json
{
  "document_id": "flow",
  "source_revision": "v1",
  "units": [{"text": "員工提出申請 → 主管審核 → IT 建立帳號。", "image_uri": "https://example.com/flow.png", "page": 3}],
  "metadata": {"filename": "manual.pdf"}
}
```

#### 0.1.5 既有 Docling 官方文字摘錄：重新包裝成一個 Unit

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

## 1. 唯一共用 Schema

[JSON Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/parsed_document.schema.json) 是形狀來源；[validate.py](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/validate.py) 檢查補充語意。

| 頂層欄位 | 型別 | 規則 |
|---|---|---|
| document_id | string | 必填非空文件識別 |
| source_revision | string | 必填非空來源版本；自動產生政策仍由 Q-007 定案 |
| units | list[dict] | 必填非空、有序列表；每筆直接放欄位，不包 fields、不要求 unit_id |
| metadata | object | 必填，可為 {}；文件層資訊，Chunk 預設完整繼承 |

頂層禁止未知鍵；移除 fields 與 structure。Unit 是欄位集合，沒有 children、parent 或遞迴 Unit 協定。內容欄位沿用 JSON 值能力，允許複製業務資料；物件型欄位不會被通用 Chunker 當成另一棵文件結構遍歷。Parser 若有需要可自行提供 unit_id，平台不強制、不依賴它。

預設每筆提供字串 text。共用 Schema 不強制 text，以保留進階自訂切分欄位；選定的 split_field 必須在每個 Unit 存在且為非空白字串，copy 欄位亦須存在。異質 Units 不能靠靜默略過缺欄位；Parser 應先正規化成所選任務可處理的欄位集合。空文件／空白頁處理由 Parser 政策明示，不能把空白 Unit 當作成功可搜尋內容；空白頁來源可記 metadata。

## 2. Parser 與 Chunker 分工

| 責任 | Parser | Chunker |
|---|---|---|
| 文件解碼、OCR、閱讀順序、表格／圖片轉文字 | 負責 | 不負責 |
| 決定每個獨立內容單位的邊界與上下文 | 負責，可把跨頁內容整理為同一 Unit | 尊重 Unit 邊界 |
| text-spans／page-blocks 等供應者表示 | Parser／Adapter 內部處理並展平 | 不接收這些結構規格 |
| 單筆文字內 Fixed-size／Recursive／Header-aware 切分 | 不要求實作 | 負責 |
| copy、metadata 繼承、來源範圍、Chunk ID | 提供來源內容 | 負責 |

**不跨 Unit 合併、不跨 Unit overlap。** 第一筆切 2 個、第二筆切 3 個，輸出共 5 個。小 Unit 可能產生較短 Chunk，若要合併段落，Parser 先整理成同一 Unit。每個任務選一個 Chunker；移除依 structure.schema_id 選 Chunker 的 Router，Parser 依輸入格式派送仍保留。

Header-aware 讀取 Unit 中的 Markdown #／##，不要求 heading Block。Parser 要保留標題與其內文於同一 Unit，或把上下文複製到各 Unit。標題與內文分成不同 Units 後，Chunker 不跨筆恢復關係。超長章節可再用 Recursive；其參數及無標題時的明確策略由 Component 宣告，不能無聲換方法。

### 2.1 metadata 的描述與處理提示（D-52）

ParsedDocument.metadata 可攜帶合法附帶資訊，或由下游 Component 明確支援的文件層提示，例如 chunking_mode=passthrough；Parser 依自身規則保存／產生，Chunker 按約定讀取。Unit 仍是平面內容物件，不新增根層 processing／options。metadata 的型別與允許鍵仍受共用 Contract 及適用 Component 的資料規格／參數驗證；D-67 不再要求頂層 document_schema，細節見 [24](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/24_component_io_schema_refinement.md)；模型、連線及 Secret 不因而搬進 metadata。詳細缺省與 passthrough 語意見 [15 §4.1](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md)。

## 3. 來源追溯與欄位傳遞

Chunk.fields 保持單一 dict：`ParsedDocument.units[i][split_field] → Chunk.fields[output_field]`。選定 copy 欄位取自同一 Unit，完整原文需要時明確映射 original_text，不能覆蓋切片。

Component 選擇提供 Chunk.metadata._rag.source_refs 時，使用 unit_index（0-based）、field、output_field、role 及文字 start／end。位置以該版本 Unit 的來源字串為基準，Unicode code point、半開範圍 [start,end)，不是整份文件 offset，也不是 Token／UTF-16／PDF glyph offset。unit_index 可由 Component／SDK helper 記錄，不要求 Parser 提供，也不要求所有 Chunker 輸出來源引用。

page、slide、sheet、section_title、image_uri 等自訂來源欄位不會因存在就自動複製；要供下游使用需納入 copy。文件 metadata 仍全繼承；可信 metadata 保留區政策見 Q-006。原生解析樹不再是共用契約，必要時由 Parser 保存於追溯 metadata／外部 artifact，不讓 Chunker 重新解讀。

## 4. 取捨與驗收

- 共用 Schema 統一後，仍須檢查所選欄位型別、文字格式、Tokenizer 與模型上限。
- 表格整體轉 Markdown 後，按長度切分可能破壞列或丟掉表頭；Parser 可採逐列文字以避免。特殊保護策略尚未因此核定或實作。
- 圖片沒有 OCR／描述時，不應填空 text 並宣稱可檢索；缺資源及不支援格式需明確回報。
- Header-aware、Recursive、Fixed-size 都只在 Unit 內運作；實際 Tokenizer／演算法實作驗收與資料形狀測試分開。
- 測試需包含多 Unit、特殊字元、缺欄位、空內容、copy 衝突及不跨 Unit；ordinal／來源還原只驗收有宣告提供的追溯能力，不因缺少 _rag 拒收。

## 5. Parser 相容性與驗證範圍

| 候選 Parser | 新契約的映射方向 | 本次狀態 |
|---|---|---|
| Docling | 依閱讀順序將文字／表格等整理成 Units；必要的標題上下文由 Adapter 附帶 | 已將既有官方文字摘錄重新包裝並驗證；未重跑完整 provider 測資 |
| MinerU | 將頁面／元素結果整理成 Units，保留需要的來源欄位 | 映射方向可行；新版完整 Adapter 與測試待開發 |
| MarkItDown | Markdown 整份一個 Unit，或 Parser 先整理成數個 Units | 不再需要產生 text-spans；新版實際解析整合待驗證 |
| PyMuPDF4LLM | Markdown 一個 Unit，或逐頁文字各成 Unit；Layout 資訊在 Parser 內處理 | 新版空白頁／跨頁／表格策略與整合待驗證 |

這是來源表示的設計對照，不是供應者直接輸出本 Schema 的承諾。0.1 的舊規格／官方測資對照已歸檔至 [歷史 ParsedDocument 0.1](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/history/superseded/parsed_document_0.1.md)，供查驗、不作新版驗收證據；[固定測資清單](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/provider_cases.json) 仍供後續重驗。

本次本地驗證是 [test_contract.py](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/test_contract.py) 的新正負案例及 [Docling 摘錄](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/docling_report_excerpt.json)，未執行外部模型或重新量測解析品質。

## 6. 遷移與 UI

0.2 是不相容草案變更：移除舊頂層 fields／structure，替換為 units；不以別名靜默兼容。舊結構如何展平由 Parser／Adapter 決定，不能只改鍵名丟掉邊界／上下文。Chunk SourceRef 同步升為 0.2，Inference 引用同一版本。

Parser／展平策略改動可能改變 Unit 順序、切片及索引，需重新 Ingestion。相同 source_revision 下 Parser 版本變化的 identity／發布政策仍在 Q-007／Q-008，不以 unit_index 解決版本衝突。

UI 預覽、欄位候選、Header-aware 條件與舊結構路由移除列入 [UIB-014](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/10_ui_adjustment_backlog.md#uib-014-flat-units)，本次不改 Prototype。

