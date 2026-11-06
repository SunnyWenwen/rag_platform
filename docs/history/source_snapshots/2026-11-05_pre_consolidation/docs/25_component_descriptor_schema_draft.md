> 歷史來源快照：docs/25_component_descriptor_schema_draft.md；來源 commit 916734ac0bbe0631a205bfd52626ce332aa7beb2。2026-11-05 整合後不再作現行規格；相對連結固定到來源版本。現行入口：[README](https://github.com/SunnyWenwen/rag_platform/blob/docs/rag-system-factory/README.md)。

# 25 — B：Component Descriptor Schema 初版與待決策項目

2026-11-05｜**格式候選稿，尚未核定或發布正式 SDK／Meta-schema。**沿用 D-67 已確認的六類宣告能力；本次提出具體包裝、規則、範例及待決策事項，不將新鍵名視為已通過決策。背景：[20 B 大盤](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/20_contract_inventory_responsibility_matrix.md)、[24 已確認行為](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/24_component_io_schema_refinement.md)、[12 表單／相依規劃](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/12_component_schema_ui_contract.md)。

## 1. 討論順序與本稿交付

先核定 B 的核心描述、I/O 細化與選項語意，再完成 [23 System Config](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/23_system_config_schema_draft.md) 的整合表示。D 的 component_id／implementation_version／parameters 骨架可保留，不必等所有 Component 都開發完。第一批用 Parser、Chunker、Embedding 與 Remote 區段驗證格式。

本次提供 [descriptor.schema.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/descriptor.schema.json)、[範例入口](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/README.md)及五組完整對照。Schema 檢查包裝，Engine 還要檢查 Schema 支援子集、路徑、來源、能力、I/O 接線與執行資料；格式合法不等於已可執行。

| 交付 | 現行狀態 |
|---|---|
| D-67 的責任／六類能力 | 已確認；本稿不能放寬共用 A Contract |
| 本稿 JSON 包裝／規則／版本 | 供討論，DS-01～DS-13 尚待核定 |
| Config／資料與預期 I/O Schema | 離線 fixture；expected_* 是人工明列的預期結果 |
| 真正細化解析器、Registry、Renderer、API／Manifest 接線 | 未實作；不以本輪驗證冒充完成 |

## 2. Descriptor 共同骨架

以下是結構示意，省略的內容請依範例檔閱讀，不是可直接執行的完整 Descriptor：

```json
{
  "descriptor_version": "component-descriptor/0.1-draft",
  "component_id": "example.embedding.api",
  "implementation_version": "1.0.0-fixture",
  "title": "Embedding API 欄位映射",
  "description": "將選定文字欄位轉成命名向量。",
  "scope": {"pipeline": "ingestion", "modules": ["embedding"]},
  "config_schema": {"type": "object"},
  "io": {"input": {}, "output": {}},
  "data_rules": [],
  "option_sources": [],
  "ui_hints": {},
  "rules": [],
  "resources": []
}
```

| 欄位 | 初版必要性 | 定義與提供者 |
|---|---|---|
| descriptor_version | 必填 | Admin 的描述／規則格式版本，與實作版本分開 |
| component_id／implementation_version | 必填 | Developer 的穩定識別與固定交付版本；不使用 Python class 名稱選用 |
| title／description | 必填 | 名稱、用途與限制，純文字 |
| scope.pipeline／modules | 必填 | 所屬 Pipeline 與有序連續 Module 清單；支援單一／跨 Module |
| config_schema | 必填 | User 參數的 JSON Schema；無參數時明確空物件且拒絕額外參數 |
| io.input／output | 必填 | 公開邊界的共用 Contract 引用、容器形狀及固定附加限制 |
| data_rules | 可省略為空 | 依 Config 產生欄位／限制的有限規則；固定 I/O 可不用 |
| option_sources | 可省略為空 | 指定參數從上游／當前輸出規格或可信服務資訊取得候選 |
| ui_hints／required_ui_features | 可省略為空 | 控制項、順序、分組與必要 UI 語意；不承擔資料合法性 |
| rules | 可省略為空 | 約束、名稱唯一、適用性；直接 API 提交也驗證 |
| capabilities | 可省略 | requires／provides 的已登錄能力與版本，可用 when 指定適用條件；實際能力仍受有效 Config／A 驗證 |
| resources | 有資源需求時提供 | 邏輯資源 ID／類別、服務／Profile 參數與可選 when；URL／Secret 在 E。CPU／Memory 等未機器化交付仍依 11／C／E 規格 |
| compatibility／execution_capabilities | 適用時提供 | Engine／SDK 介面相容與 Async／Batch／Streaming 宣告；具體版本政策待 DS-12 |
| change_impact／maintainers | 適用時提供 | 參數變更影響、維護者；七項交付責任仍依 11，不因欄位可省略就免交測試／說明 |

本稿針對 Ingestion 五個與 Inference 三個 Module。M6 Evaluation 不取消；其專用邊界如何納入另議。Runtime 仍共用 Flow，逐次 input／config／Context 分開，不因 Descriptor 定案改成每個 System 一個 Flow。

## 3. scope、Contract 引用與接線

```json
{
  "scope": {"pipeline": "ingestion", "modules": ["parsing", "chunking", "embedding"]},
  "io": {
    "input": {"contract_ref": "urn:retrieval-builder:fixture:ingestion-document:2026-11-05", "shape": "direct"},
    "output": {"contract_ref": "urn:rag-builder:chunk:0.2-draft", "shape": "list"}
  }
}
```

- modules 必須在固定 Pipeline 中連續且順序正確，不重複宣告 start／end。Engine 檢查邊界與既有 A 相容，不允許 Parser 宣告隨意改成 QueryContext。
- shape=direct 表示直接使用該 Contract；shape=list 表示該 Contract 的清單。若 Contract 本身就是 QueryContext[]，用 direct，避免多包一層。
- contract_ref 是核可 Contract Registry 的固定識別。共用檔現有 $id 直接沿用；沒有 $id 的 IngestionDocument 在 fixture 使用日期別名，**沒有改寫 A 或發布新共用版本**。
- io.constraints 是附加資料限制；io.output.inherit 複製同名容器的已知輸入規格，例如 Embedding 保留 fields／metadata／既有 vectors。input 不使用 inherit。
- inherit／copy 宣告的是 Schema 保留，不替 Component 執行資料複製；資料／識別／metadata 的實際傳遞仍須遵守 A。異質輸入只繼承共同保證，不以聯集捏造每筆都有的欄位。
- Remote 由一個 operation 推導 B，只公開區段的 Input／Output；不要求內部中間物件。Local Factory／Remote Manifest 的接線放 Registry／C，不在 Descriptor 填 Python import 或服務 URL。
- Indexing 的業務結果／逐項回執包裝仍待 A 的 SDK 核定；不把單一 IndexBinding Schema 冒充所有工作回傳資訊。

## 4. $ref 與邏輯相依分開

| 關係 | 候選表示 |
|---|---|
| 共用 DenseVector、Chunk、重用 Config 子型別 | JSON Schema 的 $ref／$defs |
| System 選 Component | D 的 component_id＋implementation_version；Registry 查 B |
| 公開邊界引用共用 Contract | io.*.contract_ref，由 Registry 轉成可驗證 Schema |
| Config 決定輸出名稱／條件／Schema 值 | data_rules，不用 $ref 當作參數運算 |
| 上游輸出決定下游選項 | option_sources＋rules／能力驗證 |

$ref 只接受本地 $defs 或核可／隨版本交付的 Contract 識別，不任意下載 Developer URL。URI 可以是識別而非可連線網址。資料細化結果可用 allOf 套用共用與附加限制；不能用它覆蓋或放寬共用 Contract。局部 $defs／$ref 屬於原 Schema 的資源範圍；Engine 組合時必須保留／解析原本的 $id 與基準位置，不能直接搬移片段讓引用改指其他根。具體封裝策略待 DS-06／13。

## 5. data_rules：兩個操作表達六類能力

初版以 declare／copy 加上有限組合表達六類能力；是否改成更多專用操作見 DS-04。

| 欄位 | 語意 |
|---|---|
| id／action | 規則識別；declare 宣告細節，copy 沿用來源規格 |
| side／target | input 或 output；target 指向「一筆公開資料」中的物件容器，如 /content、/units/*、/fields、/vectors |
| name | 輸出／需求欄位名稱，可為常數、Config 或目前映射項目的值 |
| schema | declare 的固定 JSON Schema，不把變數混進 JSON Schema keyword 值 |
| schema_bindings | 將已知值填進 schema 指定 keyword，例如 type、const、minItems；填完必須再驗 Schema／共用相容性 |
| source | copy 的來源 side／container／name；不讀實際資料取得型別 |
| required | 預設 true；是否必須存在。來源不是保證可取得時，不可宣稱必填 copy 成功 |
| for_each | 只展開 Config 內已宣告的清單，如 /mappings；不是任意程式迴圈 |
| when | 布林／選項條件，與 rules 共用受限條件式 |

值表達式只提供三類：{"value": 常數}、{"scope":"config","path":"/參數"}、{"scope":"item","path":"/本筆映射欄位"}。需要 Profile／能力資訊時可讀 scope=context 的可信 facts；它不是含 Client／Secret 的 RunContext。item 只在 for_each 範圍內可用。

when／constraint 使用 eq、ne、lt、lte、gt、gte、in、contains、exists，並可用 all／any／not 組合。未知值維持 unresolved；必需資訊未明不能套用設定。條件不執行 Python／JavaScript／任意遠端呼叫。

| D-67 能力 | 本稿表示 |
|---|---|
| 固定欄位與型別 | declare＋常數 name／schema，或固定 io.constraints |
| 依參數改名 | name 讀取 Config |
| 多筆映射 | for_each＋item 的來源／輸出名稱 |
| 選擇／複製欄位 | copy＋已宣告來源，必要時改名 |
| 條件增減／固定選項切換 | when 控制規則是否適用，必要時以不同 schema 分支宣告 |
| 固定型別衍生欄位 | declare output.fields 的 string 欄位；業務模板仍由 Component 執行 |

schema_bindings 是候選的有限 Schema 建構操作，不是任意 JSON Patch。建議只允許 type／const／enum／數值與長度限制；禁止改 $ref、執行程式或放寬 A。是否採此一般機制、改成專用 Profile／型別欄位，是本輪重要決策。

## 6. Embedding A→B 完整比對

完整宣告：[embedding.descriptor.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/embedding.descriptor.json)。User Config：[embedding.config.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/embedding.config.json)。

```json
{
  "profile_id": "example.embedding/v1",
  "service_ref": "embedding.main",
  "mappings": [
    {"source_field": "text", "output_name": "text"},
    {"source_field": "summary", "output_name": "summary_vector"}
  ]
}
```

Config Schema 的 mappings 是非空 array，items 為固定物件，必填 source_field／output_name，且禁止未知參數。候選名稱採 source_field／output_name；Prototype 的 source／output 不是正式格式，遷移待議。

UI 與動態來源分別宣告：

```json
{
  "option_sources": [{
    "id": "embedding-fields",
    "target": "/mappings/*/source_field",
    "kind": "fields",
    "source": {"side": "input", "path": "/fields"},
    "filter": {"types": ["string"], "required": true}
  }],
  "ui_hints": {"fields": {
    "/mappings": {"widget": "array", "item_layout": "inline", "separator": "→"},
    "/mappings/*/source_field": {"widget": "field_picker", "option_source": "embedding-fields"},
    "/mappings/*/output_name": {"widget": "text"}
  }}
}
```

此處 * 是平台定義的**路徑模式**，不是 JSON Pointer 或 $ref 自帶的陣列運算。它對應每筆映射的來源選單與名稱輸入；實際錯誤仍回具體索引。value／schema_bindings 的一般 path 不使用 *。

向量輸出的細化規則：

```json
{
  "id": "embedding-vector",
  "action": "declare",
  "side": "output",
  "target": "/vectors",
  "for_each": "/mappings",
  "name": {"scope": "item", "path": "/output_name"},
  "schema": {
    "$ref": "urn:rag-builder:chunk:0.2-draft#/$defs/DenseVector",
    "properties": {"source_field": {"type": "string"}}
  },
  "schema_bindings": [{
    "path": "/properties/source_field/const",
    "value": {"scope": "item", "path": "/source_field"}
  }],
  "required": true
}
```

這段省略完整檔的 Profile／values 欄位限制，僅示範來源綁定。完整檔另外綁定 embedding_profile_id 與已知維度；[預期輸出 Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/embedding.expected_output.schema.json) 因而要求 vectors.text／vectors.summary_vector，來源分別為 text／summary。維度來自 fixture 的可信 Profile=3，不從 User 資料或服務地址猜測。

輸出名稱重複由 rules.unique_by 檢查；與已有向量／其他規則的衝突還要共用語意驗證，不能因陣列元素不完全相同就當 uniqueItems 足夠。服務／Profile 引用由 resources 對應 E，不在映射列重填 URL／Secret。

## 7. Parser 與其他案例

| 案例 | Descriptor／Config | 可檢查的例子 |
|---|---|---|
| Parser | [宣告](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/parser.descriptor.json)／[設定](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/parser.config.json) | content.body→Unit.text；title 保留；include_page=true 加上輸入／輸出 page:integer |
| Chunker | [宣告](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/chunker.descriptor.json)／[設定](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/chunker.config.json) | text 切分、title 複製、原文 original_text、overlap < max_tokens；原文 Chunk 筆數不改欄位型別 |
| Embedding 模板 | [宣告](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/embedding_template.descriptor.json)／[設定](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/embedding_template.config.json) | 先宣告 fields.embedding_text，再映射為 vectors.text；來源 Picker 包含已知衍生欄位 |
| Remote 連續區段 | [宣告](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/remote_segment.descriptor.json)／[設定](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/remote_segment.config.json) | Parsing～Embedding、IngestionDocument→Chunk[]、parameters={}；內部資料不公開 |

每組另外提供 input、output、expected_input.schema、expected_output.schema。Parser 的輸入細節供 Ingestion 可完成的接收預檢，仍保留非空 IngestionDocument[] API、單筆 Parser Input 與背景內容驗證；不新增頂層 document_schema。

模板內引用欄位的檢查、來源資料限制與 Profile 相容性是語意能力，不因輸出欄位宣告為 string 就自動完成。內部順序建議先取得已知／衍生 fields，再推向量與下游選項；不得用輸出向量反過來生成自己的來源欄位，循環拒絕。具體分階段處理見 DS-05。

## 8. 驗證層次與本輪實際證據

| 層次 | 必須檢查 | 本輪範圍 |
|---|---|---|
| 描述結構 | 必填、型別、已知 action／widget／規則、未知欄位 | 新候選 Schema／正反例可離線驗證 |
| Embedded Schema 與靜態引用 | Draft、支援子集、受控 $ref、參數／UI 路徑與來源 ID | 離線驗證部分路徑／型別／引用；不作完整前端支援承諾 |
| Config／細化語意 | 唯一名稱、條件、copy、Profile、衍生順序、分支保證、無循環 | fixture 驗部分約束；**不執行完整 data_rules 解析** |
| 預期 I/O Schema／樣本 | 共用 Contract＋細節可驗證樣本；明顯錯誤被拒絕 | expected_* 是人工明列；驗證相符不證明解析規則與結果完全等價 |
| Runtime／UI | 真正 Parser／Tokenizer／模型、服務、相依 Picker、版本回應與部署 | 未實作；UI 記 UIB-021，使用者要求修改時才做 |

離線指令與限制見 [範例 README](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/component_descriptor/README.md)。本稿不修改共用 schemas/、Prototype 或 Runtime。完整 Registry 還要校驗六類規則不能放寬 A、多 Parser／多任務各分支可用性、能力配對及未知必要 UI feature；不以本輪測試關閉 Q-ID。

## 9. 需要決策的項目與建議

以下均為本稿具體表示的建議，並非再次要求決定 D-67 的上位需求。

| ID | 要決定什麼 | 建議 | 範例／另一選擇的影響 |
|---|---|---|---|
| DS-01 | 共同包裝與必填範圍 | 採 §2 核心必填；有相關功能才交 resources／rules 等，七項交付仍用審查清單補齊 | 固定 Parser 不必交空 UI／資源欄位；把所有欄位必填會增加最小 Component 負擔 |
| DS-02 | 單／跨 Module 範圍 | scope.pipeline＋有序 modules，檢查連續與 A 邊界 | [parsing,chunking,embedding] 只公開兩端；不重填 start/end 或任意 DAG |
| DS-03 | I/O 引用與清單包裝 | 固定 Contract Registry 識別＋shape=direct/list；附加 constraints，沿用 A | QueryContext[] 已是 List 用 direct；ParsedDocument 單型別＋list。Module-specific Wrapper／Indexing 回執尚需 A 收斂 |
| DS-04 | 六類規則如何編碼 | declare／copy＋for_each／when／schema_bindings；先用本稿案例檢查可讀性 | 另一選擇是 rename/map/vector 等多個專用 action，更直觀但規格與轉換分支較多；bindings 必須限定 keyword，不能任意 Patch |
| DS-05 | 繼承、內部衍生與順序 | output.inherit＋有序資料規則；copy 只取已知來源，先衍生 fields 再映射 vectors，循環拒絕 | Embedding 模板可選 embedding_text；來源非保證時標 unresolved／拒絕，不能把多任務欄位聯集當全體都有 |
| DS-06 | Embedded Schema 子集／引用政策 | Draft 2020-12，Schema 物件、已核定 keyword、只允許本地／註冊引用；Engine 統一 default／正規化 | jsonschema 接受某 keyword 不代表 Builder 支援；additionalProperties／nullable／default 的精確政策仍需逐項核定 |
| DS-07 | 可重複 A→B 表單與路徑 | array＋inline 排列，子欄位用 /mappings/*/source_field 指向 Picker；* 是平台模式 | 不為 Embedding 特製一個業務 widget；如要 mapping_table 專用控制項需新增必要 feature／Renderer |
| DS-08 | 一般約束／名稱唯一／UI 適用性 | 延用受限條件式，新增明確 unique_by；與 Config Schema 條件必填一致 | 同名向量兩筆來源不同仍拒絕；uniqueItems 不能代替某個欄位的唯一性 |
| DS-09 | Local／Remote 接線由誰保存 | B 只保存共同描述，Local Factory／C Manifest＋operation 由 Registry 管理，Remote 推導 B | 避免 Descriptor 重複 URL／Image／Python import；精確 C→B 來源／版本關聯另定，不加新 Remote schema endpoint |
| DS-10 | 資源／Profile 的宣告與事實來源 | resources 指向服務／Profile 參數；E 綁連線，Engine 提供只讀 Profile／能力 facts | 維度可從已解析 Profile 提供；若只填一個未知 ID，不猜維度，也不在細化時連模型服務 |
| DS-11 | 不完整草稿／失效參數／未知規則 | 草稿可保留，必要資訊未知則不能套用；失效選項可見報錯，未知必要語意拒絕 | 刪除 summary 後原映射保留報錯，不改成 text；Builder 不支援必要 UI feature 時不假裝完整表單 |
| DS-12 | 版本、相容與變更影響 | 描述版本與實作版本分開，固定引用；提供 compatibility／執行能力／變更影響材料 | implementation_version 是否強制 SemVer、版本範圍語法、撤回與遷移另定；本稿只驗非空字串，不代表自動升級 |
| DS-13 | 解析結果保存與後續 D 整合 | Engine 回傳有來源版本的 I/O／候選結果；是否 flatten／快照／Export 另定，D 仍只保存選用與參數 | allOf＋註冊引用保留來源；flatten 較易閱讀但需正確合併限制。D 的其他 SC、Manifest、M6 Evaluation 擴充仍未定案 |

建議先看 DS-01～DS-05，再用 Parser／Embedding 對照決定 DS-06～DS-10，最後核對狀態／版本／快照。沒有必要先完成全部 Component 的描述，才繼續 System Config。

## 10. 標準依據與遷移

JSON Schema 原生的 [$ref／$defs](https://json-schema.org/understanding-json-schema/structuring)、[allOf](https://json-schema.org/understanding-json-schema/reference/combining)與 [if／then／else](https://json-schema.org/understanding-json-schema/reference/conditionals)分別處理重用、共同限制與資料條件驗證；不自動把外部 Config 變成欄位名稱。本稿 data_rules／option_sources／schema_bindings 是平台候選協定，不宣稱是 JSON Schema 標準關鍵字。

12 的 component-ui-0.1-draft、單 module_type 舊片段與 Prototype 短名稱仍是舊候選／mock；本稿改用 component-descriptor/0.1-draft、scope.modules 及共同規則，需明確遷移，不保證直接相容。沒有升級原型或將舊草稿悄悄當新版資料。
