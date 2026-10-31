# Inference Contract 與 UI 設定對照

> 文件同步：2026-10-31。結果處理語意與 UI 方向已確認；正式 Config／SDK 及真實搜尋執行仍待核定／開發。

## 1. 資料基準

InferenceState → QueryContext → ResultSet → ResultItem 使用 [共用 Inference Schema](../schemas/inference_context.schema.json)。ResultItem.chunk 直接引用 [Chunk Schema](../schemas/chunk.schema.json)／[15](15_chunk_contract.md)；Embedding、索引與檢索不能各寫一份 Chunk 定義。

QueryContext 保留 query／ori_query 與來源 Query；一個 Query 可有多份 ResultSet。操作後建立新 ResultSet，保留來源清單，只有 active 選取的輸出參與下一步。歷史結果保存於同次推論的邏輯狀態；永久 Trace 的保存政策另議。

## 2. Contract 討論摘要

### 2.1 資料與控制設定分開

- `items` 是後續主要運算資料，含 Chunk、當前 score、當前 rank。
- `result_set_id` 用於選取、引用及追溯；不是由終端使用者命名的設定欄位。
- `operation` 描述已執行的方法、參數與模型；下一步由邏輯 Config 決定，不由這份歷史記錄推測。
- `source` 追蹤檢索路徑；當策略依來源加權時可供 Adapter／Engine 對應權重，普通 Generation 不需解讀。
- `score_kind` 描述分數語意，不能單靠相同字串認定跨 Query 分數可比；`score_order` 會供共用排序使用。
- Query／ResultSet 來源、歷史清單與來源項目保留在同次推論快照，可由 ID 找回；不因此要求永久保存所有 Trace。

### 2.2 三種操作與共同排序

| 操作 | 候選處理 | 分數 | 共同輸出規則 |
|---|---|---|---|
| 去重＆合併 | 選入一份或多份清單，依分組／身分鍵合併 | 依 Sum Score／RRF 等已配置策略產生；支援方法仍由 Registry 決定 | 排序、連續 rank、新 ResultSet、來源引用 |
| 取 Top N | 對每份已排序輸入保留前 N 筆 | 保留原分數與方向 | 結果仍有序；N 大於候選數時保留可用資料，不補資料 |
| 新模型算分 | 使用選定 Query 及 Chunk 欄位評分 | 產生模型新分數 | 排序、連續 rank、新 ResultSet、來源引用 |

排序為共同輸出規則，不增加第四種使用者操作。內部算分過程可以暫時無序，跨步驟可見的 ResultSet 必須符合排序契約；不對外傳 `rank=None`。同分決勝與零分／空結果等細節仍見 Q-011／Q-014／Q-023，未以 Python 穩定排序的範例行為凍結產品政策。

`group_by` 先決定選入結果的處理群組；`merge_key` 決定哪些候選視為同一身分；method 決定分數，三者分開。chunk_id 合併與同 document_id 多 Chunk 的文件分組不同，後者需挑代表 Chunk／每篇 N 個等政策，不能改寫成虛構的 Chunk。

### 2.3 ES 已融合的邊界

ES `query + knn` 可由 boost 加權相加並回傳最終 `_score`。Adapter 把這次回傳映射為一份 `stage=retrieval` 的 Hybrid ResultSet，記錄方法、欄位與權重；`input_result_set_ids=[]`、items 的 `source_refs=[]`，因平台未取得兩份獨立清單。這與 Engine 的 `stage=merge` 來源關係不同。

一般最終分數不能還原完整分項清單與各自排名。Explain 可協助分析計分，但不等於取得每路完整候選排名。向量查詢分數也不一律等於 raw cosine similarity。若要真正將 BM25 與 Vector 分開供後續合併，必須由能力支援的 Adapter 明確取回／對應，不偽造記錄。

參考：[Elastic approximate kNN query examples](https://www.elastic.co/docs/solutions/search/vector/knn/approximate-knn-query-examples)、[Search API explain](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-search)。本輪沒有連線執行 ES。

例子及可執行 Python 見 [05 §4.6.6](05_data_contracts_search_design.md#inference-state-draft)；Retrieval 的業務 Filter／ACL 仍保留，並在 Top-K 前限制合法候選。

## 3. 現行 UI 規劃

保留單一 Create／Edit 介面。Retrieval 的「進階結果處理」預設收合；Reranker 沿用原模組表單。Top N 是動作完成後的收尾設定，不新增可任意排列的操作卡片或 DAG。

### 3.1 兩層合併

| 控制項 | 新建預設 | 相依／有效範圍 |
|---|---|---|
| 同 Query 多路合併 | 勾選；Retrieval 後 | 有多個獨立 ResultSet 才融合；ES 已內部融合時顯示原因並停用 |
| 跨 Query 合併 | 勾選；Retrieval 後 | 同原始問題有多個有效 Query 才執行 |
| 每層合併時機 | 可選 Retrieval 後／Reranker 後 | 顯示有效順序，無效組合阻止套用；不默默改時機 |
| 合併策略 | RRF／Sum Score | RRF 設 k；Sum Score 設來源權重與可比性／轉換；ES 內部策略另外設定 |
| 身分合併 | chunk_id；可選 document_id | 文件模式先完成 chunk_id 融合，再於最後有效合併點選同文件最高分代表；單份清單也可文件去重 |

每個 Query 內是第一層分組，同原始問題跨 Query 是第二層。Query ID／ResultSet ID 由 Engine 管理，使用者不需手填。merge_key 選 document_id 不會產生虛構 Chunk，仍保留代表的 chunk_id 與原始引用。

### 3.2 四個固定 Top N 位置

| 位置 | 作用對象 | 停用情境 |
|---|---|---|
| Retrieval 搜尋 Top K | 每 Query／每路搜尋；ES 內部融合則是一份 Hybrid 輸出 | 無搜尋路徑是錯誤，不自動略過 |
| Retrieval 後合併 Top N | 該時點適用合併／文件去重完成後的各群組 | 該時點無處理時不參與有效設定 |
| Reranker 評分後 Top N | 每份模型評分 ResultSet；新建預設 3 | Reranker=None 時停用此上限 |
| Reranker 後合併 Top N | 後置合併／文件去重完成後的各群組 | 沒有後置處理時停用；None 不會取消必要後置合併 |

每次處理後依 score_order 排序，再取上限並重編連續 rank；沒有獨立排序開關。多份清單各自 Top N 不等於全域 Top N。後續模型與融合不能找回已截掉的候選，預覽需標出清單數與截斷位置。

### 3.3 模型與內容欄位

Reranker 預選合法的 fields.text；基本區選一個內容欄位，進階才展開其他內容設定。提問預設原始問題；逐 Query 情境可依有效計畫使用當前 Query，跨 Query 已合併則使用原始問題。內容欄位來自 Chunk，不從 ParsedDocument 臨時補欄位。

Provider 的 top_n 與平台評分後保留數分開：Adapter 應取得選入候選的完整評分，再由平台截斷；服務不支援時明示能力／限制，不隱性少回結果。正式覆蓋率／錯誤政策見 Q-003／Q-014。

Generation 使用最終有效清單，維持 chunk_template → context → prompt。Chunk 的來源位置由 metadata._rag.source_refs 產生可信引用；ResultItem.source_refs 則追溯分數與候選，兩種來源不能混用。

### 3.4 共同卡控

- 後端由 Indexing 繼承；搜尋只能選已建立索引且型別相容的欄位。
- ES 內部 Hybrid 一次只回一份清單時，不捏造分項 ResultSet 或再做同 Query 融合。獨立分路輸出須 Adapter 明確支援。
- 單 Query／單路徑停用不適用控制項並保留草稿；切回多路時恢復選擇。
- 改上游欄位／服務造成失效時保留原值，錯誤顯示 `[Module]` 與欄位；不能靜默替換。
- 展開進階不改 Config。Create／Edit／AI／預覽／匯出使用同一有效計畫；取消不修改既有 System。

## 4. 說明案例

| 案例 | Retrieval 輸出 | 有效處理順序 |
|---|---|---|
| 單 Query＋ES Hybrid | 一份已融合清單 | 略過兩層跨清單合併 → Rerank → Top 3 → Generation |
| 多 Query＋ES Hybrid | 每 Query 一份清單 | Retrieval 後跨 Query RRF → 合併 Top N → Rerank → Top 3 |
| 多 Query＋Local 多路 | 每 Query 有全文／向量清單 | 各 Query 內融合 → 跨 Query 融合 → 合併 Top N → Rerank → Top 3 |
| 先逐 Query 評分 | 各 Query 內已完成融合 | Retrieval 後合併 Top N → 每 Query Rerank／Top N → 跨 Query RRF → 後置合併 Top N |

前三個採預設時機；第四個展示進階配置。這些案例不限制合法計畫只能選固定模板；實際支援能力由 Registry／Adapter 驗證。完整資料與 Python 範例見 [05 §4.6](05_data_contracts_search_design.md#inference-state-draft)。

## 5. 實作狀態與驗收

Prototype v0.9 已有兩層時機、四處上限、卡控與清單數預覽，見 [10 §6](10_ui_adjustment_backlog.md#6-v09-實作細節展示預設與限制)；尚無真實 Engine 搜尋／融合。三份新資料 Schema 的 UI 遷移仍記 UIB-011～013。

正式驗收須涵蓋：Chunk 共用格式與可取回欄位、各 Query／來源的分數血緣、ES 已融合邊界、兩個時機與四處上限、空結果、None 與文件去重、非法相依拒絕及有效計畫與執行結果一致。Q-002／Q-003／Q-011／Q-014 保留正式 Config、Adapter、同分與分數細節；未以 UI 展示當作後端驗收。
