# Todo Enhance

## 跨 Pod Ingestion 文件鎖

**狀態：後續增強。** 現行 Runtime 以 [Pod 內記憶體](06_runtime_api_and_deployment.md#pod-local-ingestion-control)管控同文件的 Ingestion 與 Retire。當同一 System 需要由多個 Ingestion Pod 同時寫入同一個 ES 索引，且無法以流量分配避免文件重疊，再評估啟用跨 Pod 協調。

### 期望行為

- 以 `(system_id, document_id)` 作為占用鍵。索引世代與執行者身分用於核對工作仍可寫入及釋放占用。同文件的提交、首次寫入與 Retire 共用該占用規則。
- 批次一次確認並預留全部文件。有衝突時整批回 `409 DOCUMENT_BUSY`，按請求順序列出當次檢查的全部衝突，並釋放未提交的預留。不同文件可在容量允許時平行處理。
- 工作由持有 payload 的受理 Pod 執行。保護取消與首次寫入競爭，並定義 Pod 故障後的占用回收。所有者切換後，舊執行者不能釋放新占用、更新新 Run 或開始清舊。已送出的 ES 請求可能晚到，須以實際寫入批次與索引世代驗證隔離效果。

### 設計待評估

- **前版方案**使用每 System 一份 ES 控制紀錄，透過即時 Get 和 `if_seq_no`／`if_primary_term` 一次條件提交整批占用。領取、取消、首次寫入和釋放也會更新該紀錄。記錄隨活躍文件增加，熱門 System 的不同文件也會競爭同一筆紀錄。
- 評估專用鎖服務或支援交易的儲存，確認可原子預留整批占用並查出完整衝突。若採租約，定義續租、故障回收與防止舊所有者操作的條件。租約到期時須考量已送出的 Bulk 與刪除是否仍會生效。
- 以 Pod 內方案為基線，比較受理延遲、控制讀寫量、熱門 System 的重試率、ES 負載，以及鎖服務失效的影響，再決定後端與容量作用範圍。

### 驗收案例

以兩個 Ingestion Pod 和實際 ES 驗證同文件雙提交、部分重疊批次、不同文件並行、Ingestion 與 Retire 競爭、跨 Pod 取消、受理和寫入階段崩潰、索引世代切換，以及舊 Bulk 或刪除回應晚到。驗證衝突方無部分入列、舊工作不影響新批次，以及單 Pod 行為符合既有 HTTP 契約。

<a id="inference-only-config-update"></a>
## 匯入期間發布純 Inference 更新

**狀態：後續增強。** 首版發布 System Config 新版本時，仍須通過 [Ingestion 排空檢查](06_runtime_api_and_deployment.md#system-ingestion-drain)。同一 System 有排隊、執行中或待結算的匯入工作時，`update` 回 `409 SYSTEM_BUSY`。

- **判定條件。** 由 Runtime 比對目前生效版本與候選版本的有效設定。只有 Inference 行為改變，且 Ingestion 的有效設定、共用相依及 ES 索引綁定、世代與指紋均相容且未受影響，才能走此更新路徑。共用 Secret 或服務綁定若也影響 Ingestion，或影響範圍無法確認，沿用排空檢查。
- **版本切換。** 已受理的 Ingestion 與查詢固定使用各自的舊快照。發布後，新查詢在目標載入且就緒時使用新設定，Ingestion 照常收件。後續設計須確認共用 Config Revision 如何與各流程的載入版本一起核對，並處理 Builder 對不同 Pod 的發布與補載。
- **驗收。** 同一 System 有排隊或執行中的 Ingestion 時，修改查詢的 `top_n` 可成功發布，新查詢生效且匯入不中斷。修改切分、文件 Embedding 或影響 Ingestion 的共用綁定時，仍走原排空流程。
