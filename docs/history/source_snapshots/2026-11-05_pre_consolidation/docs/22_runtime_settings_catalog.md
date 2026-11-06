> 歷史來源快照：docs/22_runtime_settings_catalog.md；來源 commit 916734ac0bbe0631a205bfd52626ce332aa7beb2。2026-11-05 整合後不再作現行規格；相對連結固定到來源版本。現行入口：[README](https://github.com/SunnyWenwen/rag_platform/blob/docs/rag-system-factory/README.md)。

# 22 — Runtime 可調參數清單

更新日期：2026-11-05。決策依據：[08 D-64／D-65](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/08_implementation_plan.md)；API 行為引用 [21](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/21_runtime_ingestion_inference_api_inventory.md)，A～E 責任引用 [20](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/20_contract_inventory_responsibility_matrix.md)。

## 1. 範圍與管理方式

本文件集中記錄 Runtime 的接收大小、Queue、併發、Rate、Deadline 及工作狀態保存參數。使用者已確認前輪建議的預設與做法，並要求有固定位置整理可調參數；下表為初始開發／測試預設，不代表已量測的正式容量或已實作設定功能。

- **設定歸屬 E：Runtime 環境／資源設定。**與 D 的演算法、Component 選用、Chunk 大小及搜尋 Top N 分開；後者仍見 05／各 Component Config Schema，不在此重複列出。
- **Builder DEV**：Admin／平台部署管理者提供預設與限制，Runtime 在後端執行控制。一般 Builder User 不透過每次 Ingestion／Query body 覆寫；不因本文件新增 Admin 設定頁。
- **FTEST／ENT**：部署管理者提供同一套 Runtime 設定，可以調整上限；使用相同實作，無須連回 Builder DB。
- 表中的參數路徑是文件用候選名稱。正式檔案名稱、JSON Schema／環境變數映射、載入／重載方式與 OpenAPI 仍待實作規格核定；不因此宣稱熱更新或零停機。若套用方式需重啟，仍遵守記憶體工作／索引遺失政策。
- Runtime 總量與每 System 限制同時生效，不把每 System 上限乘以 System 數量當成總容量；個別 System 差異化覆寫、User／Workspace 額外配額及公平排程另案。

## 2. 已確認的初始預設

1 MiB＝1,048,576 bytes；大小以 bytes 計算，不以中文字數或 Base64 解碼前後混用。

| 候選參數路徑 | 調整內容／單位 | 初始預設 | 作用範圍 | 執行位置／語意 |
|---|---|---:|---|---|
| request.ingestion.max_documents | 每次提交文件數／份 | 100 | 單次 Ingestion Request | 對非空 IngestionDocument[] 計數；不是 Unit／Chunk 數，超限整批拒絕 |
| request.max_body_bytes | JSON HTTP body 大小／bytes | 20,971,520（20 MiB） | 單次 Runtime 業務 Request | 計入 JSON 與 Base64 編碼內容；HTTP 入口限制，不先接受後才當大小合格 |
| sources.max_file_bytes | URI／Base64 單份檔案大小／bytes | 10,485,760（10 MiB） | 每份來源檔案 | 以下載／解碼後內容計算；SDK resolver／相容 Component 限制。已超過此值的遠端來源可在 Worker 取得時失敗，不承諾 202 前下載完所有檔案 |
| ingestion.queue.max_waiting_per_system | 等待文件數／份 | 100 | 每 System | 只計 queued；執行中受 concurrency 控制，整批接收須一致預留容量 |
| ingestion.queue.max_waiting_total | 等待文件總數／份 | 500 | 整個 Runtime 程序 | 共用 Queue 容量，不是每 System 都額外取得 500 份 |
| ingestion.max_concurrency_per_system | 同時執行文件數／份 | 1 | 每 System | 不同文件可提高並行；同 document_id queued／running 仍拒絕重複提交 |
| ingestion.max_concurrency_total | 同時執行文件總數／份 | 2 | 整個 Runtime 程序 | 與每 System 上限共同控制；Worker 是排程概念，不要求新 Pod |
| ingestion.document_timeout_seconds | 單文件處理 Deadline／秒 | 600 | 每份已開始執行的文件 | 由 Worker 開始處理起計算；排隊等待不算入本值。逾時不等於 Remote 寫入已停止，未知結果依 API-D05 |
| inference.rate_limit_per_system_rps | 請求速率／次每秒 | 5 | 每 System | 在 Runtime 接收入口執行；具體計數／突發算法待實作，不新增未確認的 burst 參數 |
| inference.max_concurrency_per_system | 同時執行 Query 數／個 | 2 | 每 System | 同步查詢額滿直接拒絕，不進 Ingestion 的長工作 Queue |
| inference.max_concurrency_total | 同時執行 Query 總數／個 | 8 | 整個 Runtime 程序 | 各 System 共用總量，不以所有個別上限之和代替 |
| inference.timeout_seconds | 同步 Query Deadline／秒 | 60 | 單次 Query | 包含所選 Query Transformation／Retrieval／Fusion／Rerank 的整體執行；上游逾時與失敗不可偽裝成功 |
| status.retention_seconds | 可回收終態工作紀錄保存時間／秒 | 86,400（24 小時） | Runtime 記憶體工作紀錄 | 按 Run 與逐文件對應一起清理，queued／running 不因 TTL 被移除 |
| status.max_terminal_documents | 可回收終態文件紀錄上限／份 | 10,000 | 整個 Runtime 程序 | 計文件工作，不是唯一 document_id 數；超過時間或數量限制時清最舊已結束 Run，保留完整 Run／文件關聯 |

數值須為有效正值；份數、bytes、併發數及紀錄數為正整數。每 System 的 Queue／併發上限不得超過對應 Runtime 總上限。完整驗證錯誤、設定格式與套用接口留 Q-002／Q-017／Q-019，不把候選路徑當成已發布機器 Schema。

HTTP body、檔案及文件數限制各自生效。例如單個 Base64 檔案解碼後低於 10 MiB，不代表多份檔案合計一定低於 20 MiB Request 上限；JSON content 仍受 body 限制，Parser 可另宣告更嚴格內容限制。

## 3. 容量、失敗與保存行為

- 接收時先做整批快速預檢、同文件忙碌檢查及容量預留，再建立 Run／queued 狀態並回 202。不做部分入列；來源取得、昂貴 Parsing、Embedding／Indexing 仍由 Worker 執行。
- 每 System 配額／Rate 額滿與 Runtime 整體無容量要可區分；21 的 HTTP／錯誤碼表仍需完整 OpenAPI 對齊，不因本表凍結所有錯誤 code。
- Inference 使用同步入口，額滿直接拒絕，首期不新增短等待 Queue 或 async Query 工作 API。
- 完成、失敗與可安全回收的 Run 以時間與數量雙重限制保存，任一到達即清理最舊已結束 Run；不能只刪文件最新對照卻留下錯誤 Run 彙總，或無界保存全部歷史。
- 查無工作紀錄回 unknown；狀態保存不等於索引保存。Runtime 重啟仍不恢復工作，即使 24 小時未到也可能查不到紀錄；ES／MongoDB 資料可能仍存在。
- Remote 寫入結果不明時不自動重試，也不因記錄清理推定副作用不存在；unknown 紀錄回收、再次提交及查核仍沿用 API-D05。10,000 是可回收終態紀錄控制，不是整個程序記憶體 bytes 配額。
- 調整併發須驗證 Component、Client 與索引的安全性；本文件不取消 D-60 的無 Query 讀寫鎖政策，也不新增分散式 Queue／多副本一致性承諾。

## 4. 文件摘要與分頁參數

D-65 已確認摘要回應為 documents[]＋next_cursor，每筆 document_id＋source_revisions[]，由實際 Chunk 去重彙整；source_revisions 不代表最新成功版或版本歷史。下列分頁參數先留候選規格，後續定稿，不混入 §2 已確認的 14 項 Runtime 控制預設：

| 候選參數／規則 | 前輪建議 | 狀態 |
|---|---|---|
| documents.list.default_limit | 每頁 100 份唯一 document_id 的摘要 | 待確認 |
| documents.list.max_limit | 每頁最多 1,000 份唯一 document_id 的摘要 | 待確認 |
| 文件清單排序 | document_id 升冪 | 待確認 |
| Cursor | Runtime 產生、綁定目標 System；最後一頁 next_cursor=null | 待確認 |
| 清單一致性 | 不加快照；分頁途中更新資料可能改變清單 | 待確認 |

分頁分批取得文件摘要清單，不改變 Ingestion Batch、Parser Units、Chunking 或 Retrieval Top N。例如已有 250 份文件，每頁 100 份時，依序取得 100、100、50 筆摘要；一份文件即使有多個 Chunk 或來源版本，也只列一次，各版列在該筆 source_revisions。API／來源與候選格式見 [21 §9.3](https://github.com/SunnyWenwen/rag_platform/blob/916734ac0bbe0631a205bfd52626ce332aa7beb2/docs/21_runtime_ingestion_inference_api_inventory.md)。

## 5. 文件維護與驗收待辦

之後新增／修改 Runtime 控制參數，需在本表記錄名稱、單位、預設、作用範圍與執行位置，並同步環境設定 Schema、驗證及部署說明；目前尚未交付該機器 Schema／實作。模型／HTTP Client 的逐次 timeout、重試及檔案暫存保存規則若另行定案，再納入對應表，不把它們假裝已由整體 Deadline 完整決定。

實作驗收至少覆蓋：文件數／body／來源大小邊界、整批容量預留、每 System 與全域限制同時生效、Query 額滿拒絕、處理逾時、終態 Run 整組清理、活躍工作不被 TTL 清掉、重啟 unknown，以及 Builder DEV／FTEST／ENT 使用相同控制。這是未來驗收要求，不是已通過的 Runtime 測試。
