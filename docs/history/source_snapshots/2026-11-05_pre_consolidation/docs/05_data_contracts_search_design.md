> 歷史來源快照：docs/05_data_contracts_search_design.md；來源 commit 916734ac0bbe0631a205bfd52626ce332aa7beb2。2026-11-05 整合後不再作現行規格；相對連結固定到來源版本。現行入口：[README](https://github.com/SunnyWenwen/rag_platform/blob/docs/rag-system-factory/README.md)。

# Retrieval Builder — 共用資料模型與 Config 規格

> 2026-11-05 D-56：文件級完整覆寫、非同步工作／記憶體狀態、Runtime Queue／Inference 流量控制已確認，詳細 API 盤點見 [21](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/21_runtime_ingestion_inference_api_inventory.md)。工作狀態是 Runtime 管理資料，不改 IngestionDocument／ParsedDocument／Chunk／QueryContext；完整 Config／發布實作仍有待決。

> 文件同步：2026-11-05 · 開發規格草案（正式 SDK／Config 尚未凍結）
>
> 本文統整資料流、設定與版本規則；三份資料的精確形狀由 schemas/ 與 13～15 單一維護。已確認語意作為開發基準，完整 Config／SDK 仍待 Q-002 凍結，目前沒有 Engine 可直接執行。

## 1. 範圍與讀法

- 名詞意義與元件關係以 [03 §3](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/03_architecture_proposal.md#terminology) 為準；本文負責資料結構、欄位、版本規則及範例，不另定同名概念。
- 模組如何執行見 [04](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/04_module_components_io_contracts.md)，UI 見 [06](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/06_ui_development_spec.md)，HTTP 包裝／儲存見 [07](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/07_backend_runtime_integration.md)。
- 本文引用 IngestionDocument／ParsedDocument／Chunk，並統一 QueryContext[]、Config 及執行包裝的責任，避免各模組重複定義。
- 物件形狀、Contract 版本與細節待 [Q-002](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-002) 核定；ParsedDocument 四鍵／Chunk 六鍵依 D-49／D-52 保持一致。
- `?` 表示可省略，不自動表示可為 null；`JSON` 必須可序列化，數值不可為 NaN／Infinity。正式 required／nullable／additionalProperties 須由 Schema 定義。

<a id="identity-versions"></a>

## 2. 識別、版本與作用域

版本概念的正式定義見 [03 §3.4](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/03_architecture_proposal.md#version-terms)。下表是對應的欄位用途與未決實作政策；其中 source_revision 指匯入 Retrieval 的來源文件內容，不是本 repository 的 Markdown 規格版本。

| 欄位／概念 | 語意 | 狀態 |
|---|---|---|
| workspace_id／system_id | Workspace → System；System 的邏輯識別跨環境不因部署設定不同而另改 Config，授權由可信 Context 決定 | 階層／邏輯方向已確認；格式與部署識別待決 |
| document_id | 同一 System 中邏輯文件的穩定識別，不能用 Chunk ID 取代 | 已確認；產生演算法 Q-007 |
| source_revision | 文件內容版本，與 Config Revision 不同 | 已確認；省略時的生成／比較 Q-007 |
| chunk_id | Component 產生必要非空識別；fingerprint／ordinal 的可重現衍生 ID 是選用參考工具 | D-52 不強制共同 Hash 演算法；穩定／更新語意 Q-007 |
| config_revision | 平台保存的設定版本 | 已確認；草稿／生效語意 Q-015 |
| index_generation | 可追蹤的索引資料版本，不能把可變 alias 當 immutable snapshot | 已確認方向；切換 Q-010／Q-015 |
| contract_version | 資料／Config 契約版本 | 建議；遷移 Q-002 |
| run_id／request_id／trace_id | 批次工作、單次請求及追蹤識別 | 已確認方向；線上包裝 Q-019 |

CSV 每列是邏輯文件。跨批更新需映射穩定鍵；Prototype 的批次自動 ID 不能宣稱可跨次穩定。檔案拆為多份文件時保留來源資產關聯，不能讓所有列沿用同一 document_id。

### 2.1 版本變更範例與規則

以下用同一 System 的兩份來源文件 A／B，示範 03 定義的三種業務版本如何分別變動：

| 成功完成的變更 | 文件 A／B | Config Revision | 索引資料版本 |
|---|---|---|---|
| 初次匯入 | A:v1、B:v1 | C1 | I1 |
| A 原文修改並成功更新索引 | A:v2、B:v1 | C1 | I2 |
| 原文不變，改 Chunk Size 並重建 | A:v2、B:v1 | C2 | I3 |
| 只改 Query Rewrite Prompt | A:v2、B:v1 | C3 | 仍可沿用 I3 |

以上 I1～I3 是說明概念的識別，不是已選定快照實作。即使 source_revision 不變，重切／重新 Embedding／索引重建也可能形成新索引資料版本；新文件尚未成功發布時，不能先把現有索引說成已含新版內容。兩者不一對一。

不同環境的資料可不同，故相同 Config 不保證 index_generation／文件集合相同。是否保留實體不可變快照、何時生成 ID 與原子切換仍由 Q-010／Q-015 核定；此處不新增已完成的版本管理承諾。

### 2.2 collection 命名（已確認方向）

Builder 由 Workspace＋Retrieval System 名稱自動產生邏輯 collection，使用者不用手填。既有實作附穩定 System ID，避免同名及正規化碰撞；建立後改顯示名稱不重命名既有目標。UI 的邏輯名稱唯讀；各環境的 DB／實體索引目標由部署綁定及 Adapter 管理，不因實體目標不同修改處理 Config。正規化演算法、長度與匯入既有集合的權限規則仍屬 Q-007／Q-019，不重開「是否自動命名」的方向。直接 Engine 則使用 Config／可信 Binding 中明確的集合，不依賴 Builder 才可運作。

## 3. Component I/O 資料規格與欄位（D-67）

共用外層及既有限制由 13～15／schemas/ 固定；Component 在 B 宣告資料細節、參數與欄位規則，Engine 根據 D 的有效 Config 推導當前規格。取消每個 System 另外維護頂層 document_schema；完整責任與六類宣告能力見 [24](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/24_component_io_schema_refinement.md)。

| 項目 | 規則 |
|---|---|
| Unit／fields／vectors／metadata 的名稱與型別 | 固定或依所選 Component 的 Config 宣告；來源名稱唯一、輸出不得衝突，不占用平台保留欄位 |
| required／型別／文字能力 | API 共用外層與 Parser 輸入細節分開檢查；解析後及後續 Module 輸出持續驗證共用 Contract＋當前資料細節 |
| 上游選項 | 只以已宣告且相容的欄位／能力提供；未知欄位可被開放 Schema 接受，但不能冒充已知候選 |
| 任意 JSON／User 業務限制 | 有需要時由該 Parser 的設定接受欄位定義／metadata 限制；Sample 建議需確認，不重複維護全域權威 |
| 缺值／default／額外欄位 | 依核定的 Schema／正規化規則；Prototype 舊 unknown_fields=reject 不自動成為所有 Parser 的後端預設 |

預設 text 路徑不變；實際所選切分欄位須在收到的每個 Unit 存在且為非空白字串，copy 欄位亦須存在。下游只選型別／能力相容的欄位；多 Parser／多任務保留分支與可用性，不以欄位聯集保證全體都有。上游改名／移除欄位時保留失效引用並阻止套用，不自動替換。第一版精確 Filter 仍只支援字串。

**待決**：六類宣告的正式語法、default／required／nullable／空白／額外欄位政策、array 型別、保留名稱及 migration，仍見 Q-002／Q-006。正式後端不得直接沿用 Prototype 的 JavaScript 行為。

## 4. 共用業務資料

### 4.1 Ingestion 輸入與 Parser Input

API／Import／Parser 共用同一份 [IngestionDocument Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/ingestion_document.schema.json)，完整語意見 [13](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/13_ingestion_parser_input_contract.md)。document_id 必填，content／base64／uri 恰選一種；可選 source_revision、metadata、media_type、schema_id、parsing_profile。Engine 不提供 multipart，Builder／呼叫端將每份上傳轉成此單筆 JSON，再依 D-58 組成非空 List 呼叫 Runtime。以下範例是一份 item，完整 HTTP body／工作與文件管理見 [21](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/21_runtime_ingestion_inference_api_inventory.md)。

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "content": {"text": "設備每月需清潔散熱孔。", "title": "保養規範"},
  "metadata": {"department": "manufacturing"}
}
```

此例由相容的 Structured JSON Parser 將 content 鍵整理成 ParsedDocument.units 中的一筆 dict；metadata 使用外層欄位。CSV 每列映射成一份 IngestionDocument，每筆 IngestionDocument 不直接放 fields／structure／vectors。來源版本省略時的產生政策仍待 Q-007。

Parser 透過可信 Context 的共用 resolver 取得 URI 或解碼 Base64，原 IngestionDocument 形狀不變。批次 body=IngestionDocument[] 已確認；Context、資源生命週期與精確回應另見 Q-002／Q-016／Q-017／Q-019。已解析內容仍放 content 並使用相容 Adapter，不等於直接接收 Chunk 或向量。

### 4.2 ParsedDocument：四個固定頂層 key

> **2026-11-02：ParsedDocument 0.2-draft**。以 [14](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/14_parsed_document_contract.md) 與 [Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/parsed_document.schema.json) 為唯一來源。

| Key | 型別 | 語意 |
|---|---|---|
| document_id | 非空 string | 文件 ID |
| source_revision | 非空 string | 來源內容版本；生成政策另議 |
| units | 非空 list[dict] | 有序、獨立的平面內容單位；直接放 text 等欄位，不包 fields、不要求 unit_id |
| metadata | object | 文件業務與受控追溯資訊，可為 {} |

Parser 整理來源結構為 Units；Chunker 僅在每筆文字內切分，不跨筆合併或 overlap。移除頂層 structure 與結構路由；Header-aware 使用當筆 Markdown 標題，Fixed-size／Recursive 使用字串與 Tokenizer。

[單筆文字](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/plain_text.json)、[多筆 Units](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/units.json)、[表格逐列](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/parsed_document/table_rows.json) 共用同一形狀。來源參照為 unit_index＋field＋Unicode 字元範圍。舊供應者結構報告不能當成新版通過證據，詳見 14 §5。

### 4.3 Chunk：六個固定頂層 key

> **2026-11-02：已有可驗證 0.2 草案（D-47／D-49），尚未凍結 SDK**。精確形狀與語意以 [15 Chunk Contract](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md) 及 [同一份 JSON Schema](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/chunk.schema.json) 為目前來源；共用情境／資料見 [cases.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/chunk/cases.json)。

| Key | 責任 |
|---|---|
| chunk_id | 必要非空識別，由 Component／SDK helper 產生；fingerprint＋ordinal 僅為參考策略 |
| document_id、source_revision | 繼承文件；只改切分設定不改來源內容版本 |
| fields | 預設只切 text 並寫回 text；需要時進階選切分／輸出／完整複製欄位 |
| vectors | Chunking 為 {}；Embedding 寫入 values＋embedding_profile_id＋source_field 的命名物件 |
| metadata | 繼承合法文件 metadata，可含 Component 支援的處理提示；_rag 追溯選填 |

基本 UI 不顯示欄位選擇，直接切 units[i].text 並輸出 fields.text；不自動複製其他 Unit 欄位。保留切分前完整原文時，才進階設定 text → original_text 或其他不衝突名稱。D-48 確認每個多欄位任務預設將片段輸出到 fields.text；有需要才複製完整來源到 original_text／original_faq 等不衝突名稱。第一版必要切分欄位缺失／型別錯誤／全空白、必要任務零產出或明確 copy 欄位缺失均報錯；可選複製暫不擴充。同一 Unit 兩個欄位各切 2／3 段時，結果串接為 5 個 Chunk，不做交叉配對；互相附帶完整原文另需明確 copy 映射。

metadata._rag 選填，由 Component 決定是否提供；有 source_refs 時使用 unit_index／field／output_field／文字範圍，有 chunking 時記錄 fingerprint／ordinal／task_id。缺少不報錯、不保證位置還原。D-54 下 ResultItem 不保存分數血緣，過程寫 Logs；不影響 Chunk 的選填文件追溯。詳見 15 §3～6。

Chunk 須自帶 Rerank／檢索結果消費端 需要的內容，不強制回查 ParsedDocument。Indexing 預設保存全部 fields／metadata；完整向量保存在索引／Chunk Store，檢索傳遞可令 vectors={}，不能因此刪除已保存內容。追溯用輔助結構可在 metadata；供下游內容選單使用則建議放 fields，不新增頂層 structure。

metadata 全部繼承限於驗證後的業務欄位及可信平台資訊，ACL／來源不能由輸入覆蓋；必要平台資訊不可排除，第一版不提供 metadata 排除選單。此規則不表示 copy_fields 自動包含所有 fields。正式可信區協定／索引發布機制仍在 Q-006～Q-010 等待決項，不能把資料草案當成已實作原子更新。

### 4.4 Embedding Profile 與 IndexBinding

2026-11-04 D-55：IndexBinding 已確認為每 System 一組、五鍵的輕量交接描述，無 index_ref／searchable。完整定義與邊界見 [19 IndexBinding 與索引格式契約](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/19_index_binding_artifact_contract.md)。

| 物件 | 必要語意 |
|---|---|
| EmbeddingProfile | 模型／版本、維度、document/query encoding、normalization、Tokenizer／revision；用 Profile 配對 Document／Query 向量 |
| IndexBinding | artifact_type、target、fulltext_fields、filter_fields、vector_bindings；由 Indexing 提供，Engine 驗證管理，Retrieval 透過 Context 使用 |

Component Config 定義如何處理；D-62 採共用 Flow，每次執行傳入本次參數。RunContext 提供 Engine 依已固定 Config 快照、部署設定及初始化結果準備的正確 System 資源，兩者不同；不把整份 System Config 加入公開文件／Query body。Runtime 就緒／資料版本獨立管理，不由 Binding 存在推定。僅宣告且相容的索引能力才能搜尋；Chunk 中存在／保存某欄位不代表它已建立搜尋索引。完整儲存格式／SDK／版本政策仍依相關 Q-ID。

### 4.5 Inference 與檢索輸出邊界

2026-11-03 使用者確認簡化版（D-54）；以下取代舊 inference-0.2-draft。這是開發依據，尚非已發布 SDK／已上線 API。

Inference 的業務 Input／Output 統一為 `list[QueryContext]`（JSON root array），沒有 InferenceState 外框。QueryContext 固定 ori_query、query，並提供預設空值的 filters、result_sets、metadata。ResultSet 只有 key／items；ResultItem 只有 chunk／選填 score。只傳目前有效資料，處理後替換；歷史與診斷寫 Logs。items 順序就是排名，RRF 使用陣列位置。數值 score 經 Adapter 統一為越大越好，Sum Score 仍需驗證完整分數及可比性。

| 交接 | Input | Output |
|---|---|---|
| Query Transformation | QueryContext[]，通常一筆原始問題 | 原始／衍生 QueryContext[]，複製 filters／metadata |
| Retrieval | QueryContext[]；IndexBinding／資源由 Context 注入 | 同型別，填入每 Query 的 result_sets |
| 合併／Top N／Rerank | QueryContext[] | 同型別，替換目前清單／score／順序 |
| Query API | query＋選填 filters／metadata | 直接回傳 QueryContext[] |

空命中為 items=[]；可有多筆 QueryContext／ResultSet，不隱含全域融合。執行錯誤使用獨立錯誤 Envelope；request_id、Config Revision 與計時使用 Headers／Logs，不加入成功資料 body。Chunk 沿用 15 的六鍵定義，_rag 追溯為選填。

<a id="inference-state-draft"></a>
<a id="query-context-contract"></a>
<a id="inference-kiss-discussion"></a>

### 4.6 QueryContext／ResultSet／ResultItem：已確認的簡化 Contract

機器定義：[inference_context.schema.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/schemas/inference_context.schema.json)；新的 $id 為 query-context-list-0.3-draft。檔名保留供既有連結使用，root 已明確改成 array。驗證時註冊共用 Chunk Schema，不由 Schema ID 自動下載。Pydantic 與連續範例見 [17](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/17_pydantic_contracts_draft.md)。

#### 4.6.1 欄位

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

#### 4.6.2 key、Filter 與 metadata

- ResultSet.key 是穩定的 Config 路徑／群組名稱，如 text_bm25、text_vector、merged；可用於選取與來源權重，不是 log-only。每個 QueryContext 內須唯一；不同 Query 可沿用相同 key。
- API 的 filters 與 System 預設條件全部 AND，放入初始 QueryContext.filters。Rewrite 複製它，不讓 LLM 產生或改寫。只允許已建索引的過濾欄位及 eq／in；範圍語意不在此擴充。
- metadata 預設 {}，承載 language、session_tag 等 JSON；不是 Config、Secret 或授權來源。Rewrite 複製，Rerank／Top N 保留。
- 同一次請求的跨 Query 合併才合法；filters 必須相同。本版參考實作要求 metadata 相同，衝突明確報錯，不任意選最後一筆。真正 request／ACL 身分由可信執行 Context 管理，不能只比較 ori_query 就當成同次請求。

#### 4.6.3 分數與共同排序

| 操作 | 當前有效輸出 |
|---|---|
| Retrieval | 有序 items；Adapter 將距離等數值轉為越大越好，無數值可省 score |
| RRF | 用每份清單 1-based 陣列位置：sum(1/(k+position))；結果寫入 score |
| Sum Score | 所有分數存在，且 Config 明確確認可比或提供支援的正規化；否則拒絕 |
| Rerank | 新模型分數覆寫 score，再排序及 Top N，不保留舊分數欄位 |
| Top N | 保留已排序清單前 N；不夠不補，空清單合法 |

不能把 score 寫成名次再當相關分數加總；排名已由 items 位置提供。較低距離較好的後端由 Adapter 轉換，不新增 score_order。不同來源即使都越大越好，尺度也不一定可比。同分決勝正式政策仍見 Q-011／Q-014；參考程式以 chunk_id 穩定決勝，不因此凍結所有 Component。

#### 4.6.4 合併與當前狀態

同 Query 多路合併替換該 context 的 result_sets。跨 Query 依相同 key／路徑群組處理；完成後可輸出一筆 context（query 回到 ori_query），保留未合併的其他分組。merge_key 僅 chunk_id／document_id：前者對齊同一 Chunk，後者在融合後以最高分 Chunk 代表同文件，不把同文件不同 Chunk 分數盲目加總。rank-only 的文件代表以既有排序位置選取；需跨清單比較時先建立可比較順序／融合分數。

若 ES 已內部 Sum Score／RRF，只回傳一份 key=es_hybrid 的清單與最終 score；不捏造 BM25／Vector 的分項清單、分項分數或排名。需要分路結果時 Adapter 必須真的取得各路輸出。

#### 4.6.5 五個完整例子與 Python

| 案例 | 檔案 | 讀法 |
|---|---|---|
| 多路檢索 | [01_retrieval.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/inference/01_retrieval.json) | 每 Query 多個 key／items |
| Top N 後 | [02_top_n.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/inference/02_top_n.json) | 只留當前有效候選 |
| Rerank 後 | [03_rerank.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/inference/03_rerank.json) | 目前分數與順序，沒有歷史清單 |
| 跨 Query 融合 | [04_cross_query_fusion.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/inference/04_cross_query_fusion.json) | 合併後 context，metadata 保留 |
| ES Hybrid | [05_es_hybrid.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/inference/05_es_hybrid.json) | 一份後端融合輸出 |

[python_example.py](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/inference/python_example.py) 示範 RRF、Top N、同／跨 Query 合併與替換評分；不呼叫模型或資料庫。完整 DTO 例子見 17。UI 仍是固定示意候選，不以計畫預覽冒充真實執行。

#### 4.6.6 明確遷移

舊 InferenceState、query_id／ori_query_id、active_*、result_set_id、stage、operation、source、score_kind／score_order、ResultItem.rank／source_refs 不再是這版業務物件欄位。舊 wrapper 不靜默接受；呼叫端及 Remote Service 須同步升級 Contract。Chunk.metadata._rag 未被刪除，仍是不同責任的選填文件追溯。

Config、資源與可信授權由 Runtime 注入，不因移除記錄欄位而失去控制；正式 HTTP 版本協商、錯誤及 SDK 發布仍依 Q-002／Q-019。兩層合併與四處 Top N 見 [09](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/09_inference_contract_ui_plan.md)。

## 5. 共用執行與錯誤物件

下列延續舊 04 的設計方向，正式欄位必填與狀態仍由 Q-002／Q-017 核定：

| 物件 | 建議欄位 |
|---|---|
| ModuleConfig／ComponentSelection | 23 的共同選擇草案為 component_id、implementation_version、parameters；module_type 由 slot／Descriptor 推導，I/O 版本由 Registry／SDK 核對，服務邏輯引用依所選參數 Schema；完整包裝待 SC-01／02 |
| RunContext | workspace_id、system_id、config_revision、run_id／request_id、trace_id、deadline、attempt、可信 auth_scope；環境／部署綁定另明確記錄 |
| ModuleResult[T] | status: succeeded／partial／failed，data、errors、warnings、metrics |
| ModuleError | SDK 內部錯誤草案：code、module、message、retryable、item_id?、details?；對外 HTTP／狀態 error 核心依 21 的 code／message／module，輸入驗證另附 path，不直接透出內部包裝 |
| ExecutionMetrics | duration_ms、input_count、output_count、token_usage?、provider_request_id? |

failed 時 data 為 null；partial 必須能對應成功／失敗／skipped 項目，不能默默少資料。哪些模組允許 partial 及如何提交資料仍受 Q-009 限制。HTTP 任務狀態不是 ModuleResult.status，見 07。

2026-10-29 D-43：上表以 component_id 選擇具體 Component，module_type 表示所屬 Module；它們與 Component Instance 的 node_ref 分開。D-54 之後 ResultSet 只有 key／items，已無 method／operation 等紀錄欄位；方法選擇留在 Config，過程寫 Logs。舊 Config／Prototype 的選擇欄位需按版本遷移，詳見 [03 名詞對照](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/03_architecture_proposal.md#component-terminology-migration)。

未知 Token Usage 為 null／省略，不填 0。Secret 與敏感原文不進錯誤／追蹤。使用者無權設定可信租戶／ACL Context。

<a id="config-spec"></a>

## 6. Config 結構與有效設定

### 6.1 Config 與部署設定的契約邊界

名詞定義及跨環境原則見 [03 §3.3](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/03_architecture_proposal.md#config-terms)。正式 Schema 需將邏輯設定與環境部署綁定拆開：前者保存方法、參數、Schema／欄位／Prompt、模型語意及邏輯引用，後者解析服務端點、Secret 引用、DB／實體索引與資源設定。

同一 System、同一 Config Revision 的邏輯設定跨環境一致。若要改處理方法、模型／維度／Encoding 等語意，需建立新 Config Revision 並依影響重建，不用環境覆寫掩蓋邏輯差異。不同環境仍需檢查實際模型 Profile 相容性。

原型曾把服務 URL／Secret 引用與 Pipeline 放在同一物件，需明確 migration。具體型別與檔案包裝 Q-002 未凍結，但分離方向已確認。依 03 的正式用語，正式契約不新增 Blueprint 領域物件；舊匯出型別／檔名的遷移見 06。

D-64：Runtime 的大小、Queue／並行、Rate、Deadline 及工作狀態保存設定歸 E，由 Admin／部署管理者控制，不混入每次業務 body 或 D 的演算法參數。初始預設與可調項集中在 [22](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/22_runtime_settings_catalog.md)；候選參數路徑與正式機器 Schema 不等同，尚未交付實作。

### 6.1.1 Remote Pipeline 與固定服務

D-51 的有效 Config 以整段引用保存服務識別／版本、連續範圍、邊界 Contract 與開放的邏輯參數；具體巢狀格式待 Q-002／Q-028。UI 使用第一個 Module 當入口，不因此在 Parser 私有 Config 複製整段設定。編譯時排除涵蓋 Module 的本地草稿，並拒絕重複／重疊執行。

服務 Manifest 與各環境 Endpoint／Secret／儲存綁定分開。演算法參數即使由啟動設定檔載入仍屬邏輯 Config；External 的固定模型／索引語意記入服務版本與相容資料，不把無參數表單當成無版本要求。第一版不加入 data_space_id 或 shared 開關，不修改 13～15／Inference Schema。External 固定資料空間由 Developer 管理，可能多 System 共用；平台管理的 Image 實例以啟動綁定分配獨立儲存範圍。詳見 [18](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/18_remote_service_pipeline_integration.md)。

### 6.1.2 文件 metadata 處理提示（D-52）

metadata 不只供描述／過濾，也可傳遞 Component 明確約定的文件層提示，例如 chunking_mode=passthrough。遵守共用 Contract 及適用 Component 的 metadata 細節宣告／設定，並由 Component 說明鍵名、型別、允許值、缺省／未知值處理；不是任意參數都自動生效。固定演算法／模型／服務設定仍在 Config／環境綁定，不放 Secret 或授權指令。第一版不新增全域控制欄位／規則引擎；ParsedDocument 與 Chunk 根結構不變。見 [15 §4.1](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md)。

### 6.2 草稿、有效 Config 與部署綁定

- UI Draft 保存基本／進階欄位及未啟用方法的草稿；不是所有欄位都參與執行。
- Effective Config 僅包含使用中的方法、參數、服務及欄位；AI 與手動入口共用編譯／驗證。
- 部署設定／環境覆寫只替換允許的連線／Secret／目標／運行資源，不修改 System 的邏輯 Config。
- 更換 Embedding 語意 Profile 不能當作純環境覆寫，必須重新 Embedding／Indexing。
- 使用相同服務的兩個模組引用同一 llm_ref；匯出只包含實際引用的服務。

整合初版集中見 [23 System Config Schema 草案](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/23_system_config_schema_draft.md)：D-67 後候選根結構為 contract_version、llms、pipelines.ingestion／inference；資料規格由 Component 宣告＋Config 推導，不再獨立頂層 document_schema。先前 execution 名稱沒有凍結，不再作為同時包含流程與 Runtime 限制的模糊容器；結果處理計畫放 inference，Queue／Rate／Deadline 等依 D-64 歸 E／22。Component 引用用 component_id＋implementation_version，由 Registry 取得 Descriptor.config_schema 驗證 parameters；不把完整 Descriptor／Manifest 複製進 D。System ID／Revision／IndexBinding 由可信管理與 Context 提供，完整型別／Profile／部署包裝仍待 SC 決策。

### 6.3 模組設定詞彙

下表列出語意與設定責任；精確 Config 拼字仍待凍結。資料契約採用 13～15，切分計畫與欄位路徑層次見 §7。

| 模組 | 已確認語意 | 本版建議 Config 欄位 |
|---|---|---|
| Import | JSON IngestionDocument；三種來源共用外層驗證與內容取得 | 來源限制／resolver 政策；CSV 映射屬 Builder |
| Parsing | Structured JSON 預設；相容 Parser／Adapter 自動路由 | 已啟用 Component／profile、media_type／schema_id 能力、內容映射 |
| Chunking | Fixed-size／Recursive／Header-aware；預設 text、不選欄位；進階多任務／複製；metadata 全繼承 | split_field／output_field／copy 映射與有序 tasks 草案見 15；size／overlap／tokenizer 及有效方法參數，無 metadata_fields |
| Embedding | 預設 fields.text → vectors.text；命名向量包含 Profile 識別與來源欄位 | profile、mappings（source_field、output_name）；命名可設定，預設向量名稱 text |
| Indexing | 全部 fields／metadata 保存，搜尋與過濾另外選；持久化模式跨環境固定 | Component 選擇決定後端；parameters 保存 fulltext_fields、vector_fields、filter_fields、persistence／metric 等所支援參數；無 stored_fields，collection 在 E／Binding |
| Query Transformation | None／Rewrite／Multi-query | 共同 Component 引用＋自身 parameters，例如 llm_ref／prompt／count／include_original；1／N 統一表示仍是提案 |
| Retrieval／Fusion Plan | 選已索引欄位、推導模式；可配置策略及合併時點 | fulltext_fields、vector_fields、per_route_k、top_k、filters、fusion；stages／scope／placement 具體 Schema 待 Q-014 |
| Rerank | 新模型算分的方法；服務為 None／DEV／Rerank API | 共同 Component 引用＋所支援的 service_ref／內容欄位／提問來源；模型評分後保留數在結果處理，位置候選見 23，不與 Provider 的 top_n 混用 |
| ResultSet 後處理 | 去重＆合併／取 Top N／新模型算分；共同排序 | 分組、方法與參數的正式 Config Schema 仍待 Q-002／Q-014；最新 UI 原型配置見 10 |

Query Rewrite／Multi-query 的 1／N、Structured Output 與共用 LLM Adapter 提案保留，見 04 §5.1；取消答案生成及自訂答案 JSON 設定。

正式枚舉建議用 snake_case，UI 可顯示自然語言。Prototype 的 chunking.split、embedding.mappings[].source、indexing.filters、transform 等短名稱不自動視為正式 Schema；需明確 migration。Chunk 後的引用使用 fields.text／vectors.text／metadata.department；Chunking 來源用當筆 Unit 的 key，例如 text。上述拼字及預設值需 Q-002 核定，禁止同時接受未宣告別名而掩蓋錯誤。

ResultSet 是一次執行的資料；處理計畫是可保存的邏輯 Config，ResultSet.key 依 Config 路徑／群組解析，不再使用 runtime result_set_id。§7 對照設定與資料責任；v0.9 的 UI 配置 `retrieval.processing` 僅為展示草案，不表示正式 Engine Schema 已凍結。最新對照、有效配置與未完成邊界見 [10 §6](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/10_ui_adjustment_backlog.md#6-v09-實作細節展示預設與限制)；[09](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/09_inference_contract_ui_plan.md) 整理現行兩層融合與四處 Top N 的 UI 對照。

### 6.4 參數與相依規則

| 條件 | 驗證 |
|---|---|
| Token Chunking | size 為正整數；overlap 為整數且 0 ≤ overlap < size；Tokenizer 可取得；Fixed-size 步長為 size−overlap，末塊不補齊；Header-aware 需要當筆文字的 Markdown 標題格式，不要求 heading Blocks |
| Embedding mappings | 來源為有效文字欄位；output_name 唯一；有限值、維度與 Profile 相容 |
| Indexing | 全部 Chunk.fields／metadata 保存；搜尋欄位與上游一致；必要識別／來源／ACL 強制保留；下游只需確認欄位存在、型別適合及已由 Chunking 保留，不再要求額外勾儲存 |
| Retrieval | 至少一路；每路及最終 K 為正整數；僅選已建立索引；Query Profile 由向量欄位繼承 |
| Fusion | 多 Query／多路需有明確計畫；UI 已支援同／跨 Query 各自選 Retrieval 後／Reranker 後，預設兩者勾選且在 Retrieval 後；只使用已選策略有效參數 |
| Sum Score | ES 內部 Hybrid 的預設策略；平台跨清單另可選 RRF／Sum Score。權重有限非負且使用中至少一個大於 0；可比性／轉換需顯式驗證 |
| RRF | rank 從 1；k 預設 60 且為正整數；k 與 Top-K 不同 |
| Rerank | None 不評分且不使用其 top_n，但保留必要後置合併；啟用時 top_n 為正整數、不強制 ≤ Retrieval K。四處輸出上限各自作用於對應動作；實際不足取可用數量，合併後數量可能增大 |
| Templates | 只允許宣告變數；單次替換；未知／必要變數缺少阻止保存 |
| LLM | 引用有效；刪除使用中的服務不得默默換另一個 |

純 BM25 可跳過 Embedding，但 Chunking 仍需 Tokenizer。複製欄位長度可能大於 Chunk Size，Embedding 必須逐項檢查實際輸入。Tokenizer、模型極限及溢位政策見 Q-004。

Fixed-size 的 separators／keep_separator／header_levels 保留在 UI Draft 時不參與 Effective Config、驗證或變更影響。方法名稱、size／overlap、有效 Tokenizer 及內容欄位屬執行語意；改變後需按 Ingestion 變更處理。視窗與來源位置規則見 [04 §4.3](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/04_module_components_io_contracts.md#43-chunking)。正式 method 枚舉拼字仍待 Q-002，`fixed_size` 可作候選，不新增必須支援的別名。ParsedDocument 四鍵／Chunk 六鍵不變。

「全部保存／繼承」取代舊的使用者 stored_fields／metadata_fields 投影；原型短名稱 indexing.stored／chunking.metadata 仍待正式遷移，不直接作為新的有效配置語意。舊索引未保存或舊 Chunk 未繼承的內容不會憑空補回，必要時須重新 Ingestion／重建，不能只刪 Config 欄位就宣稱資料齊全。精確遷移與 Hash／Revision 細節留 Q-002／Q-015。

**融合配置的目標要求已存在，細節尚待 Q-014**：必須能區分演算法、融合範圍（同 Query／跨 Query）與執行時點（Rerank 前／後）。已確認兩層與預設 Retrieval 後合併；正式 Config／Adapter 支援範圍、route 型別及分數細節需再核定；不能把全部合併為一個 fusion.method 後宣稱符合需求。`fusion.stages[]` 是先前助理提出的 Schema 候選，尚非已定欄位。

### 6.5 過濾條件

```json
[{"field":"metadata.department","operator":"eq","value":"manufacturing"}]
```

Indexing 宣告可過濾欄位；Retrieval 保存預設條件；Query API 可加本次條件。全部與後端強制授權 AND；in 清單內為任一值符合。第一版 eq 為非空字串，in 為非空、不重複字串清單。空條件清單不增加業務限制，不能取消 ACL。

所有 Query × 欄位路徑須在取 Top-K 前套用相同限制。缺值／null／多值精確語意與 Adapter 可用能力見 Q-013；不支援就拒絕配置。數值／日期／OR 群組列為後續。

## 7. 共用契約與設定的對照

三份資料 Schema 已有可驗證草案；完整 Engine Config／部署設定的根結構仍待 Q-002。以下列出設定責任，不提供混用 Prototype 舊欄位的完整 YAML。實際可驗證的有效切分計畫與輸出，引用 [Chunk cases.json](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/examples/chunk/cases.json) 的 effective_spec／chunks。

| 設定位置 | 設定內容 | 驗證時點／下游結果 |
|---|---|---|
| Builder 上傳映射 | CSV column → document_id／source_revision／content.*／metadata.* | 每列先驗 IngestionDocument；不屬 Engine 的切分設定 |
| Parser Component | 接受的 media_type／schema_id、content 形狀與轉換、輸出 Unit 欄位／文字格式能力 | 共用輸入＋Component 內容驗證 → ParsedDocument Schema／語意驗證 |
| Component I/O 資料規格（B） | 固定細節或依有效 Config 細化 Unit／fields／vectors／metadata；資料欄位定義必要時是 Parser 參數 | 組裝與候選驗證，以及 API／各 Module 執行輸入輸出驗證；不新增一份由 User 重填的全域 Schema |
| Chunking | 基本 text；進階有序 tasks、每任務 Component／參數、split_field／output_field／copy_fields | 逐 Unit 檢查來源欄位與文字格式相容；六鍵輸出、必要 ID／任務產出及有提供時的追溯驗證 |
| Embedding | 來源欄位、向量名稱、不可變 Profile 識別 | 預設 fields.text → vectors.text；寫入 values／embedding_profile_id／source_field |
| Indexing | 全文／向量／Filter 欄位、搜尋後端、持久化模式 | 保存全部 Chunk 內容；Binding 檢查向量來源、Profile、維度及索引能力 |
| Inference | Query、搜尋欄位／Filter、兩層融合時機與四處 Top N、Rerank／檢索結果消費端 內容欄位 | 操作 QueryContext／ResultSet；使用 Chunk 已保留的內容，不強制回查 ParsedDocument |
| 部署設定 | DEV／FTEST／ENT 的服務 URL、Secret、集合與資源綁定 | 不改變同版 Config 的邏輯；Memory／MongoDB 模式不能在 Export 時任意覆寫 |

Chunk 後的 UI／跨容器引用使用 fields.text、vectors.text、metadata.department。15 的切分計畫 split_field／copy.source_field 使用當筆 Unit 的 key；output_field 與 DenseVector.source_field 使用 Chunk.fields 的 key（例如 text）。每階段明確解析，不將舊 ParsedDocument.fields 路徑當別名。

ParsedDocument.units 每筆直接放內容欄位；Chunk 的 metadata._rag.source_refs 記 unit_index、field 與 Unit 內文字範圍，不新增 structure。完整切分 spec 由 Config／Run 保存，Chunk 可選擇保存 fingerprint／ordinal／task_id，沒有也合法。

### 7.1 D-53：兩項已確認的預設 Component 能力（v0.12 有 UI 模擬）

- 預設 Embedding Component 可選模板組合固定文字與 fields，預設關閉；輸出獨立 fields.embedding_text，沿用來源／向量映射並保存衍生文字，向量 source_field 指向衍生來源。欄位衝突／缺失與模型長度檢查須涵蓋最終內容。
- 預設 Chunker 可獨立勾選「額外保留原文 Chunk」，預設關閉；以每 Unit／任務的完整來源為準，若已有相同切片不重複產生，不跨 Unit 合併。與既有 copy 原文欄位不同。
- 兩者屬邏輯 Config，不因環境綁定而改變；不要求所有自訂 Component 實作，不新增共用資料根鍵／Pipeline Module。具體 Config 拼字尚未凍結；完整語意見 [15 §9](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/15_chunk_contract.md#embedding-field-composition)，UI 待辦 UIB-018／019。

## 8. Config 變更影響矩陣

| 有效變更 | 影響 |
|---|---|
| 影響資料規格的 Component 版本／參數、Import／Parsing／Chunking／Embedding／Indexing 的邏輯配置 | 新 Config Revision，標記需重新 Ingestion；中間產物重用另決 |
| D-53 模板／衍生欄位／映射 | 需重新組合、Embedding／Indexing；Chunk 重用依來源保留與版本政策，不保證自動局部重跑 |
| D-53 額外原文 Chunk 開關 | Chunk 集合改變，需重新 Ingestion；沿用既有資料替換／發布政策 |
| 部署設定的 DB／實體索引目標 | Config Revision 不因此改變；更新部署綁定，目標需有相容資料或重新 Ingestion |
| 同 Profile 的模型服務 URL／Secret | 邏輯 Config 不變；驗證連線與實際模型相容性，不能把不相容模型當成純換 URL |
| Query Transformation、Retrieval、Rerank、被引用的 LLM | 不需重建；需重新測試／評估 |
| Indexing filter_fields | 需重建搜尋能力 |
| Retrieval filters 詞值、本次 filters | 僅影響查詢 |
| 顯示名稱 | 不更換穩定 collection |
| 未啟用／未引用服務的草稿 | 不改有效 Pipeline 或重建判定 |

「舊評估失效」是不能代表新版，不等於刪除歷史報告。Prototype 清除示意值的行為不應直接變成正式歷史資料刪除政策。

CSV 映射保存、Revision 計算、canonical JSON／Hash、部署綁定是否可重用資料版本需 Q-015 核定。邏輯 Config Hash 不混入部署 URL／認證／資料目標；部署綁定另記版本／識別以追蹤實際環境。不得記真實 Secret；有語意順序的陣列不可任意排序。

### 8.1 「重新 Ingestion／索引重建」的範圍

重建需說明受影響資料與需要重做的步驟，不一律代表清空整個資料庫。先前 Q-010／Q-015 的討論主要指有效 Ingestion 設定改變後，既有資料需要重新處理時的查詢可見性；以下區分不同情境：

| 情境 | 受影響範圍／需要的處理 |
|---|---|
| 新增來源文件 | 處理新增文件及其 Chunk／索引；不因新增就預設整批重建 |
| 更新單份文件內容 | 更新該文件產生的 Chunk／vectors／索引；舊片段替換與提交政策仍待 Q-008／Q-009 |
| 修改共用 Chunk Size／切分規則 | 重新處理採用該規則的既有文件，可能涵蓋此 System 全部文件；後續 Embedding／索引隨新的 Chunk 更新 |
| 更換 Embedding 語意 Profile | 針對受影響內容重算向量並建立相容的向量索引；是否可重用 Chunk 等中間產物待 Q-015 |
| 改 Indexing 欄位／Mapping | 重建或補建受影響索引能力；實際步驟由 ES／Local Adapter 及相容政策決定 |
| 只改 Query Transformation／Retrieval／Rerank／檢索結果消費端 | 不重做 Ingestion；重新測試／評估 |
| Local Memory 程序重啟 | 記憶體 Chunk／vectors／搜尋結構已遺失，需重新 Ingestion 才可 Query |
| Local MongoDB 程序重啟 | 以已保存 Chunk／vectors 恢復 FAISS／BM25／Chunk Store；相容時不需重新 Parsing／Embedding，屬索引恢復 |

D-60 已確認不因寫入阻擋 Query、不加平台讀寫鎖，接受更新期間的新舊混合；同文件重複 Ingestion 拒絕仍維持。實體提交／失敗清理、版本相容與重建策略仍待 Q-008～Q-010／Q-015，不以此承諾原子快照。

## 9. 待討論與決策

| ID | 本文件尚缺的決定 |
|---|---|
| [Q-002](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-002) | 完整 Schema、Config 分支、型別／預設值／nullable、版本與 Prototype migration |
| [Q-003](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-003) | 模型服務／Profile 的正式契約與多 Profile 範圍 |
| [Q-004](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-004) | Tokenizer、溢位、長複製欄位 |
| [Q-006](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-006) | 保留 metadata／ACL 名稱與可信來源 |
| [Q-007](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-007) | ID／source_revision 演算法與檔案派生 |
| [Q-008](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-008) | 同 ID／版本重送、更新及刪除 |
| [Q-013](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-013) | 缺值、多值與 pre-filter 精確語意 |
| [Q-014](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-014) | 已要求的融合策略／範圍／時點如何配置、路徑與預設 |
| [Q-015](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md#q-015) | Revision、Hash、Index 版本及映射變更 |

## 10. 交付與驗收要求

Q-002 核定後，開發階段需提供 Pydantic Models、可匯出的 JSON Schema、完整 Local／ES／MongoDB 範例與無效範例。相同資料在 UI／HTTP／直接 Engine 呼叫得到相容驗證結果；Unicode offset、向量維度及欄位路徑有獨立驗收資料。實作 Schema 是程式可驗證的產物，變更時同步更新本文與範例，不允許各層另創契約。





