# Inference Contract 與 UI 設定對照

> 文件同步：2026-10-31。結果處理語意與 UI 方向已確認；正式 Config／SDK 及真實搜尋執行仍待核定／開發。

## 1. 已確認的資料基準（D-54）

Inference 的業務 Input／Output 統一為 `list[QueryContext]`（JSON root array），沒有 InferenceState 外框。QueryContext 固定 ori_query、query，並提供預設空值的 filters、result_sets、metadata。ResultSet 只有 key／items；ResultItem 只有 chunk／選填 score。只傳目前有效資料，處理後替換；歷史與診斷寫 Logs。items 順序就是排名，RRF 使用陣列位置。數值 score 經 Adapter 統一為越大越好，Sum Score 仍需驗證完整分數及可比性。

共用 [Inference Schema](../schemas/inference_context.schema.json) 直接引用 [Chunk Schema](../schemas/chunk.schema.json)。範例／驗證見 [17](17_pydantic_contracts_draft.md)、資料語意見 [05 §4.6](05_data_contracts_search_design.md#query-context-contract)。filters、metadata 隨 Rewrite 複製；跨 Query 僅限同一請求與相同 filters，本版 metadata 不同則拒絕合併。

## 2. 三種操作與資料邊界

| 操作 | 目前資料輸出 |
|---|---|
| 去重／合併 | 選入清單按 Config 分組，以 chunk_id 融合；document_id 模式另選代表 Chunk |
| Top N | 保留各份有序 items 前 N；沒有新增歷史清單 |
| 新模型評分 | 覆寫 score，再排序／Top N；不要求保存舊分數 |

Config 控制下一步；ResultSet.key 可供選取及權重，不能只當記錄。items 位置為排名，沒有 rank 或 score_order 欄位；無分數可用 RRF，Sum Score 缺分數或不可比則拒絕。每次替換目前資料，診斷寫 Logs。

ES 內部 Hybrid 只形成一份 key=es_hybrid 的清單；平台沒有各路排名就不能再做一次同 Query RRF 或捏造分項分數。平台後置融合與 ES 內部融合分開。沒有額外 Generation Gate；合法計畫可回多份清單，各份保持自身順序，不隱含全域排序。

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

每個 Query 內是第一層分組，同原始問題跨 Query 是第二層。Query 以獨立 context 表示；ResultSet 以 key 對應路徑／群組，使用者不需填執行 ID。merge_key 選 document_id 不會產生虛構 Chunk，仍保留代表的 chunk_id 與來源資料。

### 3.2 四個固定 Top N 位置

| 位置 | 作用對象 | 停用情境 |
|---|---|---|
| Retrieval 搜尋 Top K | 每 Query／每路搜尋；ES 內部融合則是一份 Hybrid 輸出 | 無搜尋路徑是錯誤，不自動略過 |
| Retrieval 後合併 Top N | 該時點適用合併／文件去重完成後的各群組 | 該時點無處理時不參與有效設定 |
| Reranker 評分後 Top N | 每份模型評分 ResultSet；新建預設 3 | Reranker=None 時停用此上限 |
| Reranker 後合併 Top N | 後置合併／文件去重完成後的各群組 | 沒有後置處理時停用；None 不會取消必要後置合併 |

每次處理後按當前相關分數或後端既定順序排序，再取上限；名次由 items 位置表示，沒有獨立排序開關。多份清單各自 Top N 不等於全域 Top N。後續模型與融合不能找回已截掉的候選，預覽需標出清單數與截斷位置。

### 3.3 模型與內容欄位

Reranker 預選合法的 fields.text；基本區選一個內容欄位，進階才展開其他內容設定。提問預設原始問題；逐 Query 情境可依有效計畫使用當前 Query，跨 Query 已合併則使用原始問題。內容欄位來自 Chunk，不從 ParsedDocument 臨時補欄位。

Provider 的 top_n 與平台評分後保留數分開：Adapter 應取得選入候選的完整評分，再由平台截斷；服務不支援時明示能力／限制，不隱性少回結果。正式覆蓋率／錯誤政策見 Q-003／Q-014。

API 回傳最終有效清單。D-52：Chunk.metadata._rag.source_refs 為選填，有提供才追溯原始 Unit／文字位置；ResultItem 不另保存分數血緣，過程寫 Logs。

### 3.4 共同卡控

- 後端由 Indexing 繼承；搜尋只能選已建立索引且型別相容的欄位。
- ES 內部 Hybrid 一次只回一份清單時，不捏造分項 ResultSet 或再做同 Query 融合。獨立分路輸出須 Adapter 明確支援。
- 單 Query／單路徑停用不適用控制項並保留草稿；切回多路時恢復選擇。
- 改上游欄位／服務造成失效時保留原值，錯誤顯示 `[Module]` 與欄位；不能靜默替換。
- 展開進階不改 Config。Create／Edit／AI／預覽／匯出使用同一有效計畫；取消不修改既有 System。

## 4. 說明案例

| 案例 | Retrieval 輸出 | 有效處理順序 |
|---|---|---|
| 單 Query＋ES Hybrid | 一份已融合清單 | 略過兩層跨清單合併 → Rerank → Top 3 → 回傳檢索結果 |
| 多 Query＋ES Hybrid | 每 Query 一份清單 | Retrieval 後跨 Query RRF → 合併 Top N → Rerank → Top 3 |
| 多 Query＋Local 多路 | 每 Query 有全文／向量清單 | 各 Query 內融合 → 跨 Query 融合 → 合併 Top N → Rerank → Top 3 |
| 先逐 Query 評分 | 各 Query 內已完成融合 | Retrieval 後合併 Top N → 每 Query Rerank／Top N → 跨 Query RRF → 後置合併 Top N |

前三個採預設時機；第四個展示進階配置。這些案例不限制合法計畫只能選固定模板；實際支援能力由 Registry／Adapter 驗證。完整資料與 Python 範例見 [05 §4.6](05_data_contracts_search_design.md#inference-state-draft)。

## 5. 實作狀態與驗收

Prototype v0.12 已同步 QueryContext[]／filters／metadata，並保留兩層時機、四處上限、卡控與清單數預覽，見 [10 §6](10_ui_adjustment_backlog.md#6-v09-實作細節展示預設與限制)；尚無真實 Engine 搜尋／融合。平面 Units 已同步；Remote、模板與原文 Chunk 的模擬能力及正式整合限制見 10。

正式驗收須涵蓋：Chunk 共用格式與可取回欄位、當前 Query／ResultSet key 與分數正確性、ES 已融合邊界、兩個時機與四處上限、空結果、None 與文件去重、非法相依拒絕及有效計畫與執行結果一致。Q-002／Q-003／Q-011／Q-014 保留正式 Config、Adapter、同分與分數細節；未以 UI 展示當作後端驗收。


