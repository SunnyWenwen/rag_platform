# Inference Contract 討論記錄與 UI 整合提案

> 文件集 v0.17 · 2026-10-16 · Contract 規則記錄／UI 待討論
>
> 記錄本串 14:10～14:31（Asia/Taipei）的討論。三種操作及共同排序為已確認方向；本文的版面、控制項、Config 拼字、預設與第一版範圍均為提案。現有 Prototype／Engine 未因此實作。

> **UI 後續更新**：15:53 記錄的 [10_ui_adjustment_backlog.md](10_ui_adjustment_backlog.md)，已依 18:55 的使用者要求落實至 Prototype v0.9，驗收與限制見該文件 §6。§3～6 的獨立 Top N／任意順序卡片是早期提案；實作方向為動作附帶四處 Top N、基本／進階設定及 Retrieval 後預設合併，不據舊提案直接開發。§2 的 Contract 記錄仍保留，Engine 尚未實作。

## 1. 文件定位與確認狀態

資料欄位以 [05 §4.6](05_data_contracts_search_design.md#inference-state-draft) 為主責；Engine 執行以 [04 §5.2.1](04_module_methods_io_contracts.md#result-processing) 為主責；UI 原則見 [06](06_ui_development_spec.md)。本文集中對話摘要、UI 提案與討論案例，不另創一份不同的 Contract。決策狀態見 [08 D-34／D-35、Q-014](08_implementation_plan.md#q-014)。

| 狀態 | 本輪結論 |
|---|---|
| 已確認 | ResultSet 後處理收斂為去重＆合併、取 Top N、新模型算分三類 |
| 已確認 | 排序及 rank 更新抽成共同處理；每個對外輸出的 ResultSet 都已排序，rank=1 最好且連續 |
| 延續的傳遞方向 | QueryContext 擁有多份 ResultSet；同 Chunk 在不同清單的分數各自保留；下游只使用 active 選中的清單 |
| 本輪補充的情境 | ES 內部已融合時接收一份 Hybrid 清單；平台外部融合才有可引用的獨立輸入清單 |
| 草案調整 | `inference-0.2-draft` 的 stage 拼字、`source.field_paths`、跨 Query 的 q-merged 等仍待正式欄位核定 |
| UI 提案 | 在既有 Create／Edit 中增加順序式「結果處理」區；不開新主畫面，不增加通用 DAG 畫布 |

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

例子及可執行 Python 見 [05 §4.6.6](05_data_contracts_search_design.md#inference-state-draft)；其中 Top N 範例取代 v0.15 的候選分數 Filter 展示。Retrieval 的業務 Filter／ACL 仍保留，並在 Top-K 前限制合法候選。

## 3. UI 整合方案（待討論）

### 3.1 放在同一份 Create／Edit

| 既有位置 | 建議呈現 | 使用者設定 |
|---|---|---|
| Query Transformation | 沿用現有設定 | Rewrite／Multi-query、Prompt、LLM、include_original |
| Retrieval | 搜尋欄位及「輸出方式」 | 已索引欄位、每路候選數、Filter；後端內部融合或分路輸出的可用能力 |
| 結果處理（新增區塊） | 依執行順序排列的設定卡，可新增、移除、上移、下移 | 僅三種操作；方法與參數依卡片條件顯示 |
| Generation | 沿用模板與 LLM，補上最終輸入摘要 | 最終結果來源、Chunk 模板及回答 Prompt |

建議將原 Rerank 表單重用為「新模型算分」卡片中的 Rerank 設定，避免原模組與此處各自保存一套有效參數。這是版面／migration 建議，尚未移動原型。LLM、Embedding 與 Rerank 的服務格式維持既有不同能力；共用服務只引用，DEV／自行提供的部署綁定不放到處理步驟中。

### 3.2 每張卡片的欄位

| 操作 | 共同設定 | 方法設定 |
|---|---|---|
| 去重＆合併 | 輸入來源；每個 Query 內／同原始問題跨 Query | chunk_id；Sum Score 的權重與轉換，或 RRF 的 k。文件分組另需代表 Chunk 政策 |
| 取 Top N | 輸入來源 | N；作用於每份選入清單，不暗中先合併 |
| 新模型算分 | 輸入來源 | Rerank 服務、評分使用原始／當前 Query、內容欄位 |

只有一個合法輸入來源時自動帶入。多個來源時以「Retrieval 輸出」「步驟 1 輸出」等標籤選取；內部 `step_ref`／query_id／result_set_id 自動產生。一般操作接續上一步有效輸出，只有明確選入的分支才參與；歷史清單不自動回流。選取互相衍生的原始與合併清單時需偵測重複計入風險，明示錯誤／待決政策，不悄悄將同一路貢獻加兩次。

「每個 Query 內」映射到 query_id 分組；「同原始問題跨 Query」映射到 ori_query_id 分組，僅針對選中的輸出。Top N 若選到多份 ResultSet，就各自取 N；若要全域 Top N，需先以合併卡片取得一份清單。

Retrieval 的每路候選 k 控制搜尋返回量，Top N 則在已取得的候選內截取；兩者在 UI 分開標示。後續合併／模型無法找回先前已截斷的候選，預覽應標出各處截斷位置。

### 3.3 排序與追溯欄位的呈現

- 不提供獨立排序開關；顯示說明「每次處理後自動依分數排序並更新名次」。
- score_kind／score_order 由方法／Adapter 的宣告產生並唯讀；一般使用者不用手填。
- source／operation／來源 ID 不出現在基本 Config 表單，於測試結果的「執行詳情」按需展開。
- 合併演算法、權重、模型等設定仍可修改；執行後由系統記錄實際 operation，避免設定意圖與歷史輸出混用。

### 3.4 ES 原生融合的設定與卡控

Retrieval 的「輸出方式」建議提供：

1. **後端內部融合**：ES 能力支援時可選 Sum Score／RRF；每個 Query 輸出一份 Hybrid 結果。
2. **各路獨立輸出**：Adapter 支援時才可選，產生各欄位／路徑的清單，交給後續合併卡片。

後端繼承 Indexing，仍不新增 Retrieval Implementation 選單。以上是結果輸出粒度，不是第二次選搜尋後端。可用項目依已選 ES 版本／授權／Adapter 能力推導；不支援的選項顯示並停用，說明原因，不自動改為另一個計分方法。

選 ES 內部 Sum Score 後，預覽直接顯示「每 Query：1 份 Hybrid ResultSet」；不再自動加一張同 Query 的 BM25＋Vector 融合卡。跨 Query 合併仍可在使用者指定的合法位置加入。

### 3.5 模型算分與 Top N 解耦

Rerank 卡片負責模型與輸入欄位；使用者想限制候選時，增加獨立 Top N 卡，位置決定成本及結果。例如先 Top 50 再評分，與先評分全部再 Top 5 是不同計畫，不互相代換。

原型 Rerank.Top-N 及固定服務 payload 的 top_n 必須有明確遷移：UI 的結果保留數移到 Top N 卡；Adapter 若需 top_n 才能回傳完整評分，應依選入候選數請求，並驗證回傳覆蓋率。若服務無法評完，需明示能力／限制或錯誤政策，不能藉 API 預設值默默截斷。這屬待核定的 Adapter 細節（Q-003／Q-014），不能因 UI 拆卡就宣稱已實現。

## 4. 三個設定案例

| 案例 | Retrieval 輸出 | 結果處理的卡片順序 | 重點 |
|---|---|---|---|
| A：ES Hybrid，再 Rerank | 每個 Query 一份已 Sum Score 的清單 | 跨 Query RRF → 模型算分（原始問題）→ Top 5 | 單 Query 可略過跨 Query 卡；沒有額外重算 ES 內部融合 |
| B：各 Query 先 Rerank | 每個 Query 一份已 Sum Score 的清單 | 每份模型算分（當前問題）→ 每份 Top 20 → 跨 Query RRF → Top 5 | 截斷發生在跨 Query 融合前，保留清單排名供 RRF |
| C：欄位與 Query 分兩層 | 每個 Query 有全文／向量等多份清單 | 每個 Query 內 Sum Score → 跨 Query RRF → 模型算分 → Top 5 | 展示兩層合併；選用支援分路輸出的 Adapter |

案例不是僅能選 A／B／C 的固定模板，使用者可在合法順序中安排操作。數值 20／5 是說明例子，不是核定預設。範本只協助起步，套用後仍顯示完整可編輯步驟。

下列僅為 UI 意圖的 Python 草圖，不是正式可執行 Config Schema：

```python
steps = [
    {"ref": "cross_query", "type": "merge", "input": "retrieval", "scope": "original_query", "method": "rrf", "k": 60},
    {"ref": "rerank", "type": "model_score", "input": "cross_query", "model_ref": "reranker-a", "query_source": "original", "content_fields": ["fields.text"]},
    {"ref": "answer_top", "type": "top_n", "input": "rerank", "n": 5},
]
```

實際 Config 只引用邏輯步驟與服務，不保存一次執行才存在的 ResultSet ID；Engine 展開到各 Query／群組後再產生 ID。Backend／DEV Runtime／FTEST／ENT 使用同一份邏輯計畫，只有服務連線綁定不同。

## 5. Validator 與結果預覽

### 5.1 建議卡控

| 條件 | UI／Engine 應檢查 |
|---|---|
| 操作順序／來源 | 只引用上游步驟、無循環、刪除上游後保留失效引用並阻止儲存 |
| ES 已融合 | 沒有實際取得的 BM25／Vector 子清單不能選，也不能顯示虛構 rank |
| RRF | 輸入必須有各自有效 rank；取 Top N 後以保留下來的候選排名參與 |
| Sum Score | 明列路徑權重、方向／轉換與是否正規化；不同尺度的相加不是相同影響力；不擅自啟用正規化 |
| 模型算分 | 模型服務有效、內容欄位存在、Query 來源合法；合併後不存在唯一「當前改寫問題」時，需選原始問題或明確策略 |
| Top N | N 為正整數；N 超過當前候選數回傳可用筆數；未來若支援零值需另定 |
| 文件去重 | document_id 不當作 chunk_id；代表片段與計分策略未選定時不當作已支援 |
| Generation | 建議每個原始問題有一份最終有效清單；若仍有多份，要求使用者明確合併，這是待討論的 UI Gate |

錯誤沿用 `[模組／步驟] 原因`，例如 `[結果處理：步驟 2] 來源步驟已刪除`、`[Generation] 有兩份最終結果，請指定合併方式`。不以停用 Save 取代可定位的說明。

### 5.2 預覽與真實測試分開

- 儲存前的靜態預覽：Query 分支、預期每組清單數、合併時點、各階段候選上限；以「上限／依實際結果」標示，未知數量不填成確定值。
- DEV Inference 執行後：每步輸入／輸出份數、候選數、score／rank、來源、使用 Query／模型；可對比合併及 Rerank 前後。
- 只顯示實際取得的分項分數；ES 只有總分時顯示總分。來源詳情按需展開，不要求模型前端知道各後端儲存結構。
- 靜態示例不假裝真實模型試跑；沒有 Runtime 時標示模擬，延續現有產品界線。

## 6. 建議實作順序與待討論事項

本輪只整理文件／草案 Schema／資料例子；沒有修改 HTML Prototype、正式 Engine、服務或部署。

1. 先討論下列 UI 選項與 Config 意圖；不因有 JSON Schema 就視為畫面已核定。
2. 核定後調整 Prototype：卡片順序、條件欄位、靜態輸出預覽、失效引用、Create／Edit／匯出一致性；搜尋／模型仍標示模擬。
3. Engine／Adapter 實作時再驗證真實排序、分數、候選數、模型覆蓋率與 ES 能力；接入共同 Registry／Validator。
4. Runtime／Builder／獨立部署使用同一份經核定計畫；僅 Inference 變更時重測，不重建已相容的索引。

| 討論項目 | 建議起點 | 需要確認的影響 |
|---|---|---|
| UI-01：設定放哪裡 | 統一結果處理區＋順序卡片，重用原 Rerank 表單 | 是否接受將原本 Rerank 的模型設定移入此區；避免兩份配置 |
| UI-02：第一版結果粒度與文件去重 | 依 Adapter 顯示 ES 內部融合／分路；跨 Query 與同 Query 均可安排；文件去重先定「每篇保留代表 Chunk」規則 | 分路支援範圍、文件代表如何選、需要每文件 N 個嗎；未核定不造完整支援 |
| UI-03：Generation 最終清單 | 每個原始問題一份最終有效結果；多份時明確合併後才進 Generation | 是否接受以 Validator 要求明確合併，或另設多清單 Context 政策 |

以上項目由 Q-014／Q-025 追蹤，欄位與版本由 Q-002，服務限制由 Q-003；沒有重開已確認的「可設定合併時點」需求，也沒有以三個案例限制所有合法路徑。
