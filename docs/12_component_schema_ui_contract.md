# Component 設定 Schema、動態表單與相依規則

日期：2026-10-28。狀態：**D-42 已確認規劃方向與操作行為；`component-ui-0.1-draft` 為待 M0 核定的介面草案，尚未實作。**

2026-10-29 D-43 命名更新：本文的 Component、component_id、BaseComponent、目錄 components 與規則 target.kind=component 取代舊擴充單位名稱；Descriptor 草案現稱 component-ui-0.1-draft，未改既有規則／I/O 語意。舊名對照見 [03 §3.8](../03_architecture_proposal.md#component-terminology-migration)，不表示已發布相容轉換 API。

本文件細化 [04 Engine 規格](04_module_components_io_contracts.md) 與 [11 Component 開發指南](11_component_developer_guide.md) 的設定描述機制；決策狀態以 [08](08_implementation_plan.md) 為準。UI 實作統一追蹤 [10 UIB-010](10_ui_adjustment_backlog.md#uib-010-component-catalog)，不修改目前 Prototype。

## 1. 目的與已確認行為

Module Developer 宣告 Component 的參數、顯示需求及相依能力；Engine 彙整核可方法，Builder 依描述產生 Component 選單與設定表單。沿用固定的 RAG Builder Create／Edit 流程，不增加通用 DAG 畫布。

已確認的操作行為：

1. 相依不滿足的選項仍顯示，但停用並說明原因。
2. 與當前分支無關的欄位不顯示，例如 Memory 不展開 MongoDB 連線設定。
3. 進階設定預設收合；錯誤仍出現在摘要並可定位展開。
4. 上游變更使已選欄位／服務／方法失效時，保留選擇並報錯，不靜默替換；建立／套用執行設定前必須修正。
5. Builder 尚未支援的必要控制項或描述格式明示不支援，不能假裝完整設定完成。

使用者可以繼續編輯無效草稿；這不等於允許儲存為可執行的 ConfigRevision。是否將編輯草稿持久化到 DB 仍依 Q-016／Q-025，既有正式儲存／套用驗證不能繞過。

## 2. 三類描述與責任邊界

| 描述 | 定義內容 | 權威來源 |
|---|---|---|
| Module I/O Contract | 執行資料的型別與語意，例如 IngestionDocument、ParsedDocument、Chunk、ResultSet | 04 的接線、13～15／schemas/ 的資料定義、05 的 Inference；Component 必須符合 |
| Component Config Schema | 特定方法的參數、型別、必填、預設值與限制 | Component 的 `config_type`；Engine 驗證 |
| UI hints | 同一參數如何呈現、順序、進階區與控制項需求 | Component 宣告；Builder 轉換成前端控制項 |

上述為 I/O、設定及顯示三類描述，並非三份 Ingestion 資料 Schema。另以能力、選項來源及相依規則描述可組裝條件；不能以 UI hints 改變 I/O Contract，或讓隱藏欄位跳過必要驗證。ParsedDocument／Chunk 已有 [14](14_parsed_document_contract.md)／[15](15_chunk_contract.md) 可驗證草案，正式凍結仍見 [Q-002](08_implementation_plan.md#q-002)。D-47 的 Chunking 預設直接使用 text，split／copy／多任務選項只在進階顯示；共用有效 Config 仍由 Engine 解析，隱藏欄位不免除必要驗證。

`rag_engine` 管理 SDK、Registry、Component 宣告、Config 編譯與驗證；`rag_platform` 經 Runtime API 取得資料並呈現表單，不安裝所有 Component packages。AI 助手／Python／CLI 使用同一 Engine 規則。Component 目錄／驗證 API 邊界見 [07 §5.8](07_backend_runtime_integration.md#runtime-capability-contract)。

<a id="component-descriptor"></a>

## 3. Component Descriptor 草案

Descriptor 是純 JSON 資料。以下是設定／表單部分的共用包裝，不取代 11 的七項交付清單；維護者、資源、I/O 版本、執行能力及變更影響仍需交付，完整 Component Manifest 的整合由 Q-002／Q-022 核定。

| 欄位 | 必要性 | 語意 |
|---|---|---|
| `descriptor_version` | 必填 | 本描述格式與規則語意版本；本稿為 `component-ui-0.1-draft` |
| `component_id`、`module_type`、`implementation_version` | 必填 | Component 識別、所屬 Module、實作版本；不以 Python class 名稱識別 |
| `title`、`description` | 必填 | 選單名稱與用途／限制；以純文字呈現 |
| `config_schema` | 必填 | 方法參數的 JSON Schema；無參數的方法也提供明確空物件 Schema |
| `ui_hints` | 可省略，預設空物件 | 基本型別可用預設表單；特殊顯示另宣告 |
| `option_sources` | 可省略，預設空物件 | 動態欄位／服務候選來源及選用約束，屬 Engine 可驗證的設定契約 |
| `capabilities` | 可省略，預設空集合 | `requires`／`provides` 的平台能力名稱與版本；沒有額外需求也須符合 Module I/O |
| `rules` | 可省略，預設空陣列 | 參數關聯、適用條件及需要定位的相依檢查 |
| `required_ui_features` | 可省略，預設空陣列 | 需要 Builder 明確支援的元件／語意；不能省略實際必要能力 |

Registry 驗證必要欄位、JSON 可序列化、Schema 可支援程度、欄位路徑、選項來源、規則型別及能力名稱。未知會影響驗證的關鍵字／規則不得忽略；無效宣告不能作為已核可方法發布。目錄顯示哪些核可但不可用項目依權限決定；不是掃描所有 repo 中的 class。

Component 描述與版本在同一交付版本內固定，不為每個 Workspace 另寫一份 Schema。當前欄位、LLM 清單及索引狀態由帶版本的 Context 提供，不把即時選項寫死在 Component 的 `enum`。

## 4. SDK：宣告設定型別，父類別輸出 Schema

延用 11 的 `config_type`。建議共用父類別提供 `config_schema()`，從設定型別產出 Schema；各 Component 不必重寫 Schema 轉換。`ui_hints()` 預設回傳空物件，需要時覆寫。`config_type` 雖不是 abstract method，Registry 仍強制檢查；各 Module 的執行介面繼續由對應 ABC 定義。

以下只示意設定描述，沒有實作完整 SDK、Registry、Module `run()` 或驗證器：

```python
from abc import ABC
from typing import ClassVar
from pydantic import BaseModel, ConfigDict, Field


class BaseComponent(ABC):
    config_type: ClassVar[type[BaseModel]]

    @classmethod
    def config_schema(cls) -> dict:
        return cls.config_type.model_json_schema(mode="validation")

    @classmethod
    def ui_hints(cls) -> dict:
        return {}


class FixedChunkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_field: str = Field(default="fields.text", title="主要切分欄位（進階）")
    tokenizer_ref: str = Field(title="Tokenizer")
    max_tokens: int = Field(default=500, ge=1, title="Chunk Token 上限")
    overlap_tokens: int = Field(default=50, ge=0, title="重疊 Token 數")


class FixedChunker(BaseComponent):
    config_type = FixedChunkConfig
```

`overlap_tokens < max_tokens` 另由下述共用規則驗證；不假設 Python 自訂 Validator 都會自動輸出成 JSON Schema。進階 Python 語意檢查由核可 Engine／Component 程式執行，需回標準問題格式，不傳送 Python／JavaScript 給瀏覽器執行。

描述取得不可要求先實例化模型、下載權重、連線 ES／DB 或取得 Secret。Python import 本身仍是執行程式，沿用同 repo 審查／受控載入政策；可讀取 Schema 不代表不受信任程式已被隔離。

## 5. Config Schema 的第一版支援範圍

規劃使用 JSON Schema Draft 2020-12，前後端 Validator 必須測試同一子集，不以各套件的預設 dialect 猜測。Pydantic 與前端表單套件的版本、轉換層及限制於 M0／M1 鎖定。

| 類別 | 首版規劃 |
|---|---|
| 基本型別 | string、integer、number、boolean、object、array；是否允許 null 必須明示 |
| 物件 | properties、required、additionalProperties；方法設定預設拒絕未知欄位 |
| 固定選項／數值 | enum、const、minimum／maximum、exclusiveMinimum／exclusiveMaximum |
| 字串／陣列 | minLength／maxLength、items、minItems／maxItems、uniqueItems |
| 說明與初值 | title、description、default；格式說明不冒充已執行檢查 |
| 組合與參照 | 本地 `$defs`／`$ref`、allOf、if／then／else；nullable 的明確型別聯集 |
| 暫不提供任意自動表單 | 外部 URL `$ref`、遞迴型別、模糊的 oneOf／anyOf 分支、任意自訂關鍵字；需要時先擴充支援與測試 |

Pydantic 輸出的等價形式若不在核定子集內，須由受測轉換器處理或在註冊時拒絕，不能刪除限制讓它看似相容。`format` 不作為唯一正確性依據；URL、服務引用與相關語意仍由 Engine 檢查。

預設值由 Engine 的共用 Config 正規化流程處理，僅補上缺失且適用的欄位，再驗證；不把 null／空字串／非法值當缺失，也不由 UI 自行改寫使用者的選擇。例：只將 max_tokens 改為 30，預設 overlap_tokens=50 會產生關聯錯誤，不自動縮成 29。已儲存的有效設定保存解析後值與方法版本，不隨新版本 default 漂移。

## 6. UI hints 與標準控制項

UI hints 使用平台自己的 JSON 描述，再由 Builder 映射至選定表單套件；不讓 Component 綁定 React 元件實作或前端程式碼。

| 欄位／控制項 | 用法 |
|---|---|
| `order` | 以方法參數的 JSON Pointer 陣列指定順序；未列欄位仍依 Schema 顯示，不能被遺漏 |
| `groups` | id、title、fields、advanced；advanced=true 預設收合，僅改顯示 |
| `fields` | 以參數 JSON Pointer 為 key，描述 widget、help、placeholder；標題預設取 Schema |
| text／textarea／number／checkbox | 一般字串、Prompt、多行文字、數值及布林 |
| select／multi_select | 固定 enum 或已解析的候選集合；單選／多選需符合 Schema 型別 |
| object／array | 巢狀表單／可重複項目，首版使用固定 items 形狀；錯誤回實際索引路徑 |
| field_picker／service_picker | 連結 `option_source`，候選值與合法性由 Engine 解析 |

動態來源的存在與合法選用不只寫在 UI hints；`option_sources` 本身綁定目標參數，沒有 UI 也必須驗證。Prompt 的插入變數／範例／預覽屬 Builder 共用功能，若 Component 必須依賴該功能，另列 `required_ui_features`，不是只設 textarea 就宣稱完整支援。

只有裝飾性未知 hint 可忽略並提示；未知必要 widget、規則語意或 required_ui_features 時，保留可見的方法與已存設定，禁止在該 Builder 建立／套用不完整設定。沒有自動退回任意 JSON 編輯器的入口。這是 Builder 能力限制，不表示已部署且 Engine 合法的 System 必須停止服務。

<a id="dynamic-options"></a>

## 7. 動態選項與能力 Context

`option_sources` 草案每個項目使用 `target`（參數 JSON Pointer）、`kind`、`filter`。kind 先提供 document_fields、chunk_fields、chunk_vectors、llm_profiles、tokenizer_profiles、service_profiles；filter 的合法鍵由各 kind 固定，例如資料型別、使用階段、服務類別、索引能力。這些名稱是候選協定值，不凍結 Tokenizer 的演算法或共用 Config 結構。

選項 Resolver 由 Engine 提供，依輸入 Schema、前序 Module 的有效設定／產出能力、可見的服務引用與目標 Runtime 產生候選。Embedding 不能選尚未產生的欄位；Retrieval 的可搜尋欄位必須對應 Indexing 的有效索引配置。Python／API 傳同一引用也需做相同檢查。

| 候選項目欄位 | 語意 |
|---|---|
| `value`、`label` | 穩定的參數值及顯示文字；改顯示名稱不變引用 |
| `status` | selectable／disabled／unresolved；尚未取得能力不得冒充可用 |
| `reason_code`、`reason` | 停用或未確認原因，UI 以純文字顯示 |

型別／索引能力不符的相關候選保留並停用，權限不可見的項目不因此洩漏。已選引用不在候選內時，另外保留失效選項並報錯，不自動選清單第一項。查詢失敗時保留草稿且標示未驗證，不能以空清單斷言使用者已刪除服務。

`capabilities.requires`／`provides` 使用 `{name, version}` 項目，version 首版比對核定的能力契約版本；能力名稱由平台登錄。requires 由 Engine 檢查實際上游／資源是否提供，不只比較方法名稱。provides 需依有效 Config 推導已啟用能力：ES Adapter 有全文能力不等於這個 System 已替某欄建立全文索引。

規則可讀的 `context` 是 Engine 產生的唯讀、版本化事實，例如 upstream、available_services、effective_index、derived；精確各 Module 事實型別在 M0／M2 按案例擴充。UI 不能自己宣稱具有向量索引／DEV 服務或寫入可信事實。服務清單只含邏輯引用與可呈現資訊，不含 Secret 值。

新增 Config 的相容性可依計畫中的索引能力驗證；實際 Ingestion 是否完成、索引版本是否匹配、外部服務是否連通另列執行就緒檢查。不能因尚無資料就禁止建立 RAG System，也不能因 Config 合法就宣稱已有可查詢資料。

<a id="dependency-rules"></a>

## 8. 相依規則與有效設定

規則是受限宣告式資料，不允許 eval、任意程式碼、任意 URL 或指定 Python import path。第一版先支援兩種規則：

| `kind` | 格式與結果 |
|---|---|
| `constraint` | `assert` 為應成立條件；不成立產生 error，選項／方法可停用；目前已選的無效值不得因停用而消失 |
| `applicability` | `when` 為參數是否適用的條件；不適用時依 `presentation` 的 hide／disable 顯示，保留草稿、排除該分支有效值 |

每條規則有唯一 `id`、`target`（`kind=field`＋path，或 `kind=component`）、`code`、`message`。首版不提供自動修改欄位的 action；組合只計算狀態，不以規則彼此寫值，避免隱藏的循環改寫。同一 target 的多個 applicability 條件需全部成立；presentation 必須一致，衝突在註冊時拒絕。所有 constraint 都需成立；UI 可彙整多個原因。

條件表達式草案：

- 比較：`{"op": "lt", "left": {"scope": "config", "path": "/overlap_tokens"}, "right": {"scope": "config", "path": "/max_tokens"}}`。
- 值：參數／Context 引用使用 scope＋JSON Pointer；常數使用 `{"value": ...}`。
- 第一版運算：eq、ne、lt、lte、gt、gte、in、contains、exists；`exists` 只用 left，其餘用 left／right。數值比較拒絕不同型別；in 檢查左值屬於右側陣列，contains 檢查左側陣列含右值。
- 組合：`{"all": [...]}`、`{"any": [...]}`、`{"not": ...}`；all／any 不接受空陣列。一個節點只能有一種表達式形式。
- 缺失或尚未確定的引用為 unknown，不當 false 或自行轉型；exists 對確定不存在的路徑回 false，尚未取得的 Context 仍是 unknown。採三值邏輯：all 有 false 即 false，否則有 unknown 即 unknown；any 有 true 即 true，否則有 unknown 即 unknown；not unknown 仍為 unknown。
- applicability=unknown 時保留原值並標示待確認，不先排除；必要 constraint=unknown 不能通過建立／套用驗證。可辨識的缺少參數先回 Schema 必填問題，避免同一問題產生大量衍生訊息。

以下為參數適用性片段：只有 Engine 推導出 Retrieval 後存在合併動作時，該動作的 Top N 才有效。參數路徑是本例局部形狀，不凍結 05／09 的完整 Config。

```json
{
  "id": "after_retrieval_merge_top_n",
  "kind": "applicability",
  "target": {"kind": "field", "path": "/after_retrieval_top_n"},
  "when": {
    "op": "eq",
    "left": {"scope": "context", "path": "/derived/has_after_retrieval_merge"},
    "right": {"value": true}
  },
  "presentation": "disable",
  "code": "MERGE_STEP_NOT_APPLICABLE",
  "message": "Retrieval 後未啟用合併，此步驟的 Top N 不生效。"
}
```

applicability 首版只作用於參數／參數子樹，不能藉此刪除整個必須執行的 Module。使用者選擇 None 等正式略過方法時仍依 Module 的核定流程處理。

未列出的特殊語意檢查以核可 Engine 程式實作並回相同問題格式；若會影響動態選單，Engine 另回可選狀態，Builder 不複製 Python 邏輯。跨模組能力回路由 Engine 的既定 Pipeline／組裝檢查拒絕，不讓顯示規則新增迴圈流程。

**草稿、適用性與合法性分開處理：**

1. 依固定版本描述讀取草稿及 Context，補上適用且缺失的預設值。
2. Engine 判定分支適用性，產生有效參數候選；UI hints 的收合／隱藏本身沒有刪除參數的權力。
3. 驗證有效候選的 Schema、動態引用、constraint、能力與既有完整 Config／索引相容規則。
4. 回傳預覽、可定位問題及必要的重測／重處理影響；有阻擋問題時不產出可套用的有效 Config。

先解析分支選擇與其有效預設，再處理相依參數；適用性與預設值有循環相依的宣告在註冊／編譯時拒絕。條件尚未確定時不以隨意補預設值打破循環，保留待確認問題。複合規則的依賴順序及前後端一致性必須納入 M0 fixtures。

Schema 的條件必填必須與 applicability 分支一致；禁止一面無條件 required，一面宣告該欄不適用。註冊／契約測試需涵蓋各分支。直接 API 傳入已知但不適用的參數時沿用同一排除規則並回明確提示；未知參數仍拒絕。排除項不參與執行、有效 Config Hash 或重建判定；UI 草稿保留，切回時重新驗證。

例如選 Memory 時 MongoDB 綁定不適用，可以保留於部署草稿但不進有效部署設定；刪掉向量索引後仍選向量 Retrieval 則是 constraint 失敗，**不能把該 Retrieval 當不適用而悄悄略過**。部署設定使用相同狀態原則但獨立的服務綁定 Schema；URL／Secret 不混入 Component 邏輯參數。

對「由上游固定」的欄位，例如 Retrieval 後端／跨 Query 合併後的評分問題來源，由 Engine 推導有效值並唯讀顯示來源與原因；首版不透過 set_value 規則修改。若輸入顯式值與推導結果衝突，回錯誤，不默默換值；方法不需要的顯示資訊不額外寫入邏輯 Config。正式欄位位置仍依 Q-002／Q-014。

<a id="descriptor-example"></a>

## 9. Fixed-size 設定描述範例

以下為設定切片，省略完整 Component Manifest 與既有 copy_fields／資源／I/O 宣告；不是完整可執行的 Fixed-size Config。JSON Schema 與 Python 範例語意一致，產生器可有不同排序／標題。

```json
{
  "descriptor_version": "component-ui-0.1-draft",
  "component_id": "builtin.chunking.fixed",
  "module_type": "chunking",
  "implementation_version": "1.0.0-example",
  "title": "Fixed-size",
  "description": "依 Token 視窗切分，步長為 max_tokens 減 overlap_tokens。",
  "config_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": false,
    "required": ["tokenizer_ref"],
    "properties": {
      "source_field": {"type": "string", "title": "主要切分欄位（進階）", "default": "fields.text"},
      "tokenizer_ref": {"type": "string", "title": "Tokenizer"},
      "max_tokens": {"type": "integer", "title": "Chunk Token 上限", "default": 500, "minimum": 1},
      "overlap_tokens": {"type": "integer", "title": "重疊 Token 數", "default": 50, "minimum": 0}
    }
  },
  "ui_hints": {
    "order": ["/source_field", "/tokenizer_ref", "/max_tokens", "/overlap_tokens"],
    "groups": [{"id": "field_mapping", "title": "進階欄位設定", "fields": ["/source_field"], "advanced": true}],
    "fields": {
      "/source_field": {"widget": "field_picker", "option_source": "text_fields"},
      "/tokenizer_ref": {"widget": "service_picker", "option_source": "tokenizers"}
    }
  },
  "option_sources": {
    "text_fields": {"target": "/source_field", "kind": "document_fields", "filter": {"type": "string", "available_at": "chunking_input"}},
    "tokenizers": {"target": "/tokenizer_ref", "kind": "tokenizer_profiles", "filter": {}}
  },
  "rules": [{
    "id": "overlap_lt_size",
    "kind": "constraint",
    "target": {"kind": "field", "path": "/overlap_tokens"},
    "assert": {
      "op": "lt",
      "left": {"scope": "config", "path": "/overlap_tokens"},
      "right": {"scope": "config", "path": "/max_tokens"}
    },
    "code": "OVERLAP_NOT_LESS_THAN_SIZE",
    "message": "重疊 Token 數必須小於 Chunk Token 上限。"
  }],
  "required_ui_features": ["field_picker.v1", "service_picker.v1"]
}
```

使用者選 Fixed-size 後，基本區只顯示 Tokenizer 與兩個數值欄位，預設使用 fields.text；來源欄位選擇收在進階區。實際候選需通過 System Schema／來源階段檢查。這是單一任務的設定描述示意，完整有序任務與 copy 映射見 15；Config 編譯時將 fields.text 解析為有效切分 spec 中的 text，不另訂第二種執行欄位格式。Tokenizer profile 只是穩定引用，不假設使用付費 API，也不由此範例決定 tokenizer 方法。

## 10. Runtime 回傳、定位與版本

Component 目錄包裝至少需要：`descriptor_version`、`runtime_ref`、`catalog_revision`、`components`。runtime_ref 對回精確部署／Image／Engine 版本的正式結構待 Q-019／Q-021；catalog_revision 識別該版本核可目錄。Builder 若快取，需包含目標 Runtime、目錄版本及授權範圍，不跨權限共用候選清單。

設定檢查的請求／回應關聯至少包括 draft_revision、context_revision、catalog_revision、runtime_ref。Context revision 涵蓋當前 Document Schema、上游設定／能力與可見服務清單；不把實際 Secret 內容放進回應。這是管理／設定介面草案，不改既有 Ingest／Query HTTP 回應。

驗證回傳區分：

- Engine 設定是否有效：passed／failed／unresolved，與表單是否能呈現分開。
- 欄位／方法狀態：visible、enabled、applicable、status、reason；唯讀推導值另帶來源。
- issues：code、severity、module_type、node_ref、component_id、field_path、message、related_paths。
- 尚未執行的連線／索引就緒測試：明示未檢查，不以 Config passed 代替。

`field_path` 使用相對該 Component 參數的 JSON Pointer；node_ref 識別 Config 內的具體模組實例，能處理多個 Parser／路徑，不僅靠 module_type。對整個 Component 的錯誤使用空指標；跨模組關聯使用 node_ref＋field_path。下例的 node_ref 是示意穩定引用，不凍結完整 Pipeline Config 路徑。

```json
{
  "status": "failed",
  "runtime_ref": "dev-runtime-example-v1",
  "catalog_revision": "catalog-example-1",
  "draft_revision": "draft-example-7",
  "context_revision": "context-example-3",
  "issues": [{
    "code": "OVERLAP_NOT_LESS_THAN_SIZE",
    "severity": "error",
    "module_type": "chunking",
    "node_ref": "ingestion.chunking.primary",
    "component_id": "builtin.chunking.fixed",
    "field_path": "/overlap_tokens",
    "message": "重疊 Token 數必須小於 Chunk Token 上限。",
    "related_paths": [{"node_ref": "ingestion.chunking.primary", "field_path": "/max_tokens"}]
  }]
}
```

UI 顯示 `[Chunking] 重疊 Token 數必須小於 Chunk Token 上限。`，點擊後定位對應實例／欄位；即使欄位收合或隱藏也能找到阻擋原因。錯誤文字不含憑證或原始服務敏感回應。

只有四個版本／關聯值仍匹配當前草稿與目標時才能套用檢查結果；過期回應不覆蓋新草稿。取得目錄／Context 失敗時保留設定、標示未驗證，不能沿用舊的成功結果建立／套用新版。最終提交由 Backend／Engine 再核對版本並驗證，避免 UI 檢查後狀態改變。

發布新版 Runtime 不自動升級既有 System。Builder 能理解描述版本及所有必要 UI feature 時，新 Component 才可動態選用；破壞性格式／新控制項需要相容更新。若資料／Config 本身已合法、只有 Builder 不支援必要控制項，回 UI 不支援狀態，不能誤報 Engine 契約無效。

<a id="acceptance-cases"></a>

## 11. 開發與驗收案例

下表是開發時須建立的驗收案例，**不是本輪已通過的功能測試**。

| ID | 操作／條件 | 預期結果 |
|---|---|---|
| SUI-01 | Runtime 加入使用既有控制項的核可 Chunker | 更新目標 Runtime／目錄後可選；Builder 不新增硬編碼方法分支 |
| SUI-02 | Fixed-size size=500／overlap=50，再改 overlap=500 | 前者通過，後者回 Chunking 的欄位錯誤；不自動修值 |
| SUI-03 | ES 只配置向量索引 | 全文 Retrieval 選項可見但停用；理由是缺全文索引能力 |
| SUI-04 | 已選全文 Retrieval，之後刪除其全文索引 | 保留選擇／草稿並阻止建立／套用；不得悄悄略過搜尋路徑 |
| SUI-05 | Local MongoDB 切 Memory，再切回 MongoDB | Memory 隱藏 DB 綁定且不計入有效部署設定；切回恢復草稿並重驗證；跨環境 Memory 政策不變 |
| SUI-06 | 刪除 Rewrite 正在引用的 LLM／欄位 | 保留失效引用與可定位原因；不選另一個 LLM 或欄位 |
| SUI-07 | Parser 不提供所選 Chunker 所需結構 | Chunker 選項停用／已選時報錯；不得自動 fallback 丟失結構語意 |
| SUI-08 | 進階區收合但其中有效參數錯誤 | 摘要仍顯示，點擊展開定位；收合不略過驗證 |
| SUI-09 | Component 宣告未知必要 widget／規則版本 | 明示此 Builder 不支援；不產生看似完整表單；不影響既有合法 Runtime 的服務 |
| SUI-10 | 相同設定由 UI、AI 助手、Python、HTTP 提交 | Engine 的有效值、動態引用檢查、相依問題一致；HTTP 狀態由 07 映射 |
| SUI-11 | 驗證未回時修改草稿／更換 Runtime，或目錄取得失敗 | 過期成功不得套用；保留草稿、顯示待驗證與正確目標版本 |
| SUI-12 | Config 合法但尚未 Ingestion／服務未連通 | 可區分可組裝、連線與資料就緒；不將 Config 驗證顯示為真實搜尋成功 |
| SUI-13 | 同 Module 有多個 Parser／路徑，其中一個失效 | node_ref＋field_path 定位正確實例，不把全部錯誤放到第一個控制項 |
| SUI-14 | 傳入未知參數、未知 op、互相衝突的 applicability 或非法型別 | 明確拒絕；不忽略限制、不執行描述內任意程式碼 |

實作順序：M0 核定描述／規則子集與固定 fixtures；M1 做 Registry 檢查、共用 Schema／Config 驗證及最小 Chunker；M2 擴充方法／能力與案例；M3 提供目錄、Context／選項解析與驗證 API；M4 助手重用；M5 Builder 實作動態表單、草稿狀態與完整互動驗收。M6／M7 沿用相同版本／交付檢查，不調整已確認里程碑次序。

## 12. 待核定細節與範圍

本稿提供可 review 的候選格式與案例；D-42 確認採此方向規劃，不等於所有鍵名及版本已成穩定公共 API。

- Q-001／Q-002：Pydantic／前端 Validator 的版本、Schema 子集轉換、正式 SDK／Descriptor Meta-schema、完整 Config 中的節點引用。
- Q-002／Q-019：各 Module Context 的精確型別、Component 目錄／選項／驗證 API 的路徑、授權與版本識別；不新增另一套 Ingestion／Inference I/O。
- Q-022／Q-025：能力／UI feature 名稱登錄與相容測試、具體元件樣式；操作行為已依 §1 確認，不再當作全部未決。
- 複雜圖形編輯器、任意前端 Plugin、自由腳本規則、瀏覽器 Component 程式上傳不納入首版；需要時另行擴充。

參考：Pydantic 的 [JSON Schema 產生](https://docs.pydantic.dev/latest/concepts/json_schema/)、RJSF 的 [Schema 表單](https://rjsf-team.github.io/react-jsonschema-form/docs/) 與 [uiSchema](https://rjsf-team.github.io/react-jsonschema-form/docs/api-reference/uiSchema/)（2026-10-28 查閱）。參考資料支持可行性，未替本專案鎖定前端套件；本文 UI hints／rules 是本專案草案，並非 RJSF 原生格式。
