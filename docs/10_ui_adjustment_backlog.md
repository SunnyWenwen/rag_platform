# UI 待調整清單：Inference 結果處理

> 文件集 v0.16 · 2026-10-15 15:53（Asia/Taipei）· 已確認方向／待批次實作
>
> 使用者要求先記錄，晚點與其他需求一起修改。本輪只更新文件，不修改 Prototype、Schema、Python 範例、Engine 或 API。以下 `[ ]` 代表尚未實作，不代表需求尚未確認。

## 1. 範圍與最新依據

- 14:49：Query 範圍與 ResultSet／搜尋路徑範圍分開；merge_key 限 chunk_id／document_id。
- 14:54～15:16：合併可在 Retrieval 後或 Reranker 後；Top N 為動作完成後的收尾參數，UI 固定提供四個位置。
- 15:37：基本設定可直接使用，完整設定在進階區；預設 Retrieval 後全部合併為一份 ResultSet，再進 Reranker。
- 15:53：進階區的同 Query 多路合併、跨 Query 合併預設勾選；Reranker 預設選一個 fields 下的內容欄位；其餘依前述規劃，先不實作。

本清單是最新 UI 待調整基準，取代 [09 §3～6](09_inference_contract_ui_plan.md) 早期以獨立 Top N／可任意排列操作卡片為主的提案。資料型別仍見 [05](05_data_contracts_search_design.md#inference-state-draft)，執行規則見 [04](04_module_methods_io_contracts.md#result-processing)；正式 Config 欄位、遷移與 Adapter 能力仍待相關 Q-ID 核定。

## 2. 預設狀態

| 項目 | 新建時的預設意圖 | 有效執行規則 |
|---|---|---|
| 進階結果處理設定 | 收合 | 展開不改 Config，基本／進階共用同一份設定 |
| 同 Query 多路合併 | 勾選，時機為 Retrieval 後 | 後端已融合或只有一路時直接沿用，不重算同一融合 |
| 跨 Query 合併 | 勾選，時機為 Retrieval 後 | 只有一個有效 Query 時無須跨 Query 合併 |
| 預設有效流程 | Retrieval 後完成適用的合併，輸出一份 ResultSet | 再進 Reranker／Generation；實際略過的處理須有摘要 |
| merge_key | chunk_id | 可改 document_id；文件模式保留最高分 Chunk 作代表，需分數可比 |
| Reranker 評分內容 | 預選一個合法的 fields.* 文字欄位，通常為 fields.text | 必須存在且可由索引取回；不憑空建立欄位 |
| Reranker 使用的提問 | 原始問題 | 與評分內容欄位分開；合法的逐 Query 情境才可用各自改寫問題 |
| Reranker 評分後 Top N | 3 | 啟用模型評分時作用於其輸出，實際不足三筆就回可用數量 |

新建才套用預設；Edit 沿用已保存的選擇，不能因展開進階區或切換上游設定而重設使用者配置。合併策略保留 Sum Score／RRF，四個位置的其他 K／N 及精確 Config 拼字不在本輪另訂數值或型別。

「Reranker 評分問題選 fields 變數」在本清單依前文情境解讀為 **Chunk 的評分內容欄位**，UI 使用此名稱。真正的 Query 問題來自 QueryContext，不是把 Chunk.fields 當作提問；兩者在畫面上分開標示。

## 3. 畫面與控制項待辦

- [ ] **保留單一 Create／Edit 介面**：基本區顯示常用設定，進階結果處理預設收合，兩者修改同一份 Config；不新增通用 DAG 畫布。
- [ ] **Retrieval 基本區**：保留已索引搜尋欄位、搜尋候選 Top K、既有 Filter；搜尋後端仍由 Indexing 繼承，不重新選 Implementation。
- [ ] **基本流程摘要**：顯示合併時機、範圍、模型輸入清單數與最後 Top N。預設呈現 Retrieval 後合併為一份 → Reranker → Top 3 → Generation。
- [ ] **進階的兩個合併控制項**：同 Query 多路合併、跨 Query 合併預設勾選；各自可設定 Retrieval 後／Reranker 後的合法時機，不能只留下策略下拉而固定執行位置。
- [ ] **Query／搜尋路徑範圍**：區分每個 Query 內／同原始問題跨 Query，以及各路分開／合併選取路徑。用可讀名稱顯示來源，不要求填 runtime IDs。
- [ ] **合併方法**：提供 Sum Score／RRF；Sum Score 才顯示權重／已支援的轉換設定，RRF 才顯示 k。切換保留草稿，只有有效參數參與驗證及匯出。
- [ ] **候選去重**：merge_key 僅 chunk_id／document_id；後者顯示「同文件保留最高分 Chunk」規則與分數可比要求，原 chunk_id 與引用仍保留。
- [ ] **固定四處 Top N 欄位**：依下表附在對應動作上，不要求新增獨立 Top N 卡片；排序沒有另外的開關。
- [ ] **Reranker 表單**：保留 None／DEV test use／Rerank API 及條件服務設定，直接選評分內容欄位與評分後 Top N。預設只選一個 fields.* 欄位；既有多欄位能力如保留，置於進階設定。
- [ ] **分開內容與提問**：顯示「評分內容欄位」與「使用的提問」。預設內容欄位為合法 fields.*；預設提問為原始問題，跨 Query 合併後顯示實際使用的原始問題。
- [ ] **Generation 摘要**：顯示使用的最終清單與候選上限，保留現有 LLM／模板設定及 Token Budget；不以 Top N 取代 Context 長度限制。
- [ ] **保存與版本行為**：Create／Edit／AI 套用／匯出使用一致設定；取消不修改既有系統。僅 Inference 設定改變時重測，不重建相容的索引。

### 四個固定的保留數位置

| 位置 | UI 欄位 | 作用範圍 |
|---|---|---|
| Retrieval | 搜尋後保留 Top K | 每 Query、每路搜尋輸出；後端內部融合則為 Hybrid 輸出 |
| Retrieval 後合併 | 合併後保留 Top N | 此時點適用的合併完成後，每個合併群組 |
| Reranker | 評分後保留 Top N | 每份模型評分結果；預設單一 ResultSet，Top 3 |
| Reranker 後合併 | 合併後保留 Top N | 此時點適用的合併完成後，每個合併群組 |

每次動作共同遵守：執行動作 → 依 score_order 排序 → 取 Top N → 更新連續 rank → 輸出 ResultSet。Retrieval 的後端候選取得仍受 Adapter 能力約束；這個 UI 收尾規則不表示能取回先前未取得或已截掉的候選。

## 4. 連動與卡控待辦

- [ ] **ES 已融合**：同 Query 多路合併顯示「後端已融合」，相關設定唯讀／停用；保留預設意圖及原因，不重做融合，也不造出不存在的分項清單／排名。
- [ ] **單 Query／單一路徑**：保留原草稿意圖並顯示不適用原因；有效配置略過不必要的跨清單合併。切回多 Query／多路時恢復使用者先前選擇，Edit 不強制改回勾選。
- [ ] **單份結果的文件去重**：即使只有一份 ResultSet，仍允許按 document_id 去重，不與多清單融合的適用條件混同。
- [ ] **合併時機改動**：同步更新進階控制、基本摘要、四處 Top N 的作用範圍與 Reranker 輸入；不同 Query／路徑的清單身分保留到真正合併時。
- [ ] **對應動作未啟用**：Top N 顯示但停用，保留草稿，不參與有效配置。Rerank=None 不得連同必要的後置合併一起被略過，需顯示實際等價路徑。
- [ ] **欄位與服務失效**：不符合輸入型別／未儲存的欄位顯示且停用；已選欄位或服務被移除時保留失效引用、定位錯誤並阻止儲存，不靜默換值。
- [ ] **模型提問相依**：跨 Query 合併後不假裝仍有唯一的改寫問題；使用原始問題並說明。逐 Query 評分時才開放合法的各自 Query 選項。
- [ ] **K／N 驗證**：正整數、候選不足回可用數量；不能一律要求四個數字遞減，因跨清單合併後候選可能變多。各數值清楚標示 per Query／per ResultSet／per group。
- [ ] **文件數／Chunk 數**：以文件為目標時先依文件規則去重再取 Top N；提示不同階段截斷的影響，不承諾每次都滿 N 份文件。
- [ ] **方法能力**：不支援的後端輸出／融合方式顯示且停用，附原因；不靜默更換策略。Rerank API 的內部 top_n 與候選覆蓋率需有明確 Adapter 對應。
- [ ] **錯誤定位**：沿用 `[模組／設定] 原因`，進階區收合時摘要仍顯示錯誤並可展開定位。

## 5. 後續批次實作的驗收清單

- [ ] 新建時兩個合併勾選、時機都在 Retrieval 後，進階區預設收合。
- [ ] 單 Query＋ES Hybrid：沿用一份搜尋結果，不重做同 Query 融合；Reranker 顯示單份輸入與預選內容欄位。
- [ ] 多 Query＋ES Hybrid：只做需要的跨 Query 合併，預設在 Retrieval 後產生一份輸入供 Reranker。
- [ ] 多 Query＋多路獨立輸出：範圍、方法與時機設定能正確表達來源及候選上限，預設合併後為一份。
- [ ] 將任一合併移到 Reranker 後，摘要與卡控同步，逐 Query 評分與後置合併的語意明確。
- [ ] 四處 K／N 各自保存；無對應動作時停用；Reranker 後 Top 3、候選不足及 Rerank=None 路徑均正確。
- [ ] document_id 去重保留原代表 Chunk；未儲存欄位、失效服務、非法數值與不支援能力均有可定位錯誤。
- [ ] Edit 保留原勾選／欄位／參數；取消不改系統；AI 套用與手動設定一致；DEV／自行部署維持同一份邏輯 Config。
- [ ] 原型若仍為模擬，預覽與執行詳情明示模擬，不冒充 ES／模型的真實計算。

本清單完成記錄後即可與其他 UI 需求併批修改。執行與 Config 的剩餘細節由 Q-002／Q-003／Q-014／Q-025 追蹤，本輪不把待辦標示成已實作。
