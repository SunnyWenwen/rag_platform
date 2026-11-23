# Todo Enhance

<a id="secret-reference-scope"></a>
## Secret 引用欄位限制

**狀態：首版執行欄位限制。** 允許範圍見 [System Secret](05_system_config.md#system-secret)。後續評估於 Descriptor 統一標記認證欄位，供 Renderer 提示、元件註冊檢查及診斷遮罩共用。

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

<a id="runtime-graceful-shutdown"></a>
## Runtime 收到 SIGTERM 時的優雅關閉

**狀態：後續增強。** 首版 Runtime 不保證優雅關閉。Pod 被停止時，進行中的匯入與查詢可能中斷。Builder 在失聯時顯示「Runtime 無法連線」，新 Runtime 就緒後依部署意圖 `reload`。見 [DEV Runtime 同步](06_runtime_api_and_deployment.md#builder-managed-dev-runtimes)。記憶體中的 Run 紀錄隨程序消失，之後查詢回 `unknown`，由呼叫方決定是否重送。下次成功匯入同一文件時，依[現行 ES 寫入規則](06_runtime_api_and_deployment.md#es-write-control-record)覆寫並清除當時可見的舊批次。

### 期望行為

Runtime 收到 `SIGTERM` 後依序處理。

1. `/health/ready` 立即回 `503`，再等待數秒，讓 Kubernetes 與 Istio 將 Pod 從 Service 的可用端點移除。
2. 後續抵達該 Runtime 的新匯入、查詢與管理請求回 `503 RUNTIME_NOT_READY`，並附 `Retry-After`。
3. 讓進行中的查詢完成，最長等到各請求的 Query Deadline。
4. Worker 停止領取排隊中的文件。
5. 讓執行中的文件在剩餘寬限時間內盡量完成，到期仍未完成的文件結案為 `failed`。
6. 全部收尾完成，或寬限時間將到時，由 Runtime 自行結束程序。

### 設計待評估

- `terminationGracePeriodSeconds` 的候選值約 120 秒，評估是否涵蓋端點移除等待、Query Deadline 及一般文件處理時間。單文件執行上限為 600 秒，關閉流程無須等滿。
- 確認 Istio sidecar 晚於 Runtime 關閉，讓收尾期間仍可連到 ES 與模型服務。驗證方式依叢集實際使用的 sidecar 配置決定。[Kubernetes Pod 終止流程](https://kubernetes.io/docs/concepts/workloads/pods/pod-termination/)
- 決定寬限時間到期時未完成文件使用的錯誤碼。

### 驗收案例

換版時，驗證已受理的查詢能在 Deadline 內完成，執行中的文件可在寬限內完成，逾期文件結案為 `failed`，Worker 進入停止領取階段後不再領取排隊文件。新 Runtime 就緒後，Builder 自動補載原先預期上線的流程。

<a id="dev-runtime-egress-allowlist"></a>
## DEV Runtime 出站連線限制

**狀態：後續增強。** 首版不限制 DEV Runtime 的出站目標。使用者可在 Builder 填寫 Remote API 網址，Runtime 會從叢集內發出請求，因此可能被用來存取叢集內部服務、ES 或雲端 metadata 端點。Builder 開放給一般使用者前須重新評估此 SSRF 風險。見 [Q-022](08_plan_and_decisions.md#q-022)。

### 期望行為

- DEV Runtime 的出站連線限於允許清單，包含 PLED ES、模型服務及核准的 Remote API 主機。評估用 Istio 整合出站路由，例如 `Sidecar`，或 `outboundTrafficPolicy: REGISTRY_ONLY` 搭配 `ServiceEntry`。
- 使用者需要新的 Remote API 主機時，由管理員將主機加入允許清單。
- 連線被阻擋時，回報可定位的錯誤，避免將內部服務的回應內容帶到使用者可見的錯誤訊息。

### 設計待評估

- 允許清單的管理與審核流程、Builder 是否顯示可用主機、FTEST／ENT 是否比照。
- `REGISTRY_ONLY` 控制 sidecar 如何處理未登錄的目的地。評估搭配叢集網路政策或防火牆強制出站限制，並區分 Runtime 內部依賴與使用者可指定的 Remote API 目的地，讓後者只使用核准的 API 主機。[Istio 出站策略](https://istio.io/latest/docs/reference/config/istio.mesh.v1alpha1/#OutboundTrafficPolicy-Mode) · [Istio Egress Gateway 安全考量](https://istio.io/latest/docs/tasks/traffic-management/egress/egress-gateway/#additional-security-considerations)

### 驗收案例

將 Remote API 設為叢集內部服務或雲端 metadata 端點時會被拒絕，且錯誤訊息不包含內部回應內容。經核准並列入清單的 Remote API 主機可正常呼叫。

<a id="builder-runtime-maintenance"></a>
## Builder 的 Runtime 維護入口

**狀態：後續增強。** 首版不提供 Builder 維護入口。Runtime 升版由部署方直接更換 Pod。Builder 連不上時顯示「Runtime 無法連線」，新 Runtime 就緒後延續原部署意圖，[查核並補載](06_runtime_api_and_deployment.md#builder-managed-dev-runtimes)預期上線的流程。

### 期望行為

1. 管理員在 Builder 執行「開始維護」。Builder 暫停向受影響的 Runtime 送出測試請求及自動補載，保留各 System 原部署意圖。Builder 對各已載入的流程執行 `detach` 並等待排空，畫面顯示「Runtime 維護中」。
2. 管理員更換 Runtime Pod。
3. 管理員在 Builder 執行「結束維護」。Builder 依原部署意圖對各 System 預期上線的流程執行 `reload`，查核就緒後恢復服務。

### 設計待評估

- 與 [Runtime 優雅關閉](#runtime-graceful-shutdown)的分工。優雅關閉完成後，維護入口可能只需處理畫面提示。
- 維護期間 Builder 如何回應匯入與查詢，以及哪些管理員有權開始和結束維護。

### 驗收案例

維護期間 Builder 暫停送出新的測試請求與自動補載。結束維護後，所有原先預期上線的流程恢復，原先卸載的流程維持卸載。

<a id="standalone-index-initialization"></a>
## FTEST／ENT 首次建立索引

**狀態：後續增強。** 首版的索引建立授權與部署操作入口仍由 [Q-021](08_plan_and_decisions.md#q-021)追蹤，於 M7 前確認。目前由部署方保存 Config Revision、索引世代和指紋，供 Runtime 啟動查核。本節記錄首次建索引的建議方向。

### 期望行為

建議由部署方以一次性初始化指令建立索引。Runtime 啟動時只查核。找不到預期索引可能是首次部署、世代設定錯誤、連到錯誤叢集、索引誤刪或權限不足。若自動建立空索引後繼續服務，查詢可能只回空結果而掩蓋問題。自動建立也會要求 Runtime 持有建立索引的權限，多個 Pod 啟動時可能同時嘗試建立。

1. 同一個 Runtime Image 提供初始化指令，例如 `index init`。部署方透過 Kubernetes Job 單次執行，指令依匯出的 Config 與目標環境設定產生新索引世代 UUID，一次建立含 mapping 與 `_meta` 的索引，並輸出世代與指紋。若目標索引已存在，拒絕建立並回報原因。
2. 部署方將輸出的世代及指紋寫入部署設定。
3. Runtime 啟動時核對索引名稱、`_meta` 與 mapping。若找不到索引或查核不符，維持未就緒並回報原因。
4. Runtime 就緒後由部署方匯入資料。
5. 重建時，以新 Config 執行初始化取得新世代，更新部署設定並重新部署。查核新世代可用後，以獨立的刪除指令移除舊世代索引。

### 設計待評估

- 初始化及刪除指令的名稱、參數與所需的 ES 權限。
- 重送時如何沿用同一操作及原索引世代，並與部署 Bundle 整合。

### 驗收案例

首次部署可由初始化指令建立索引並啟動 Runtime。指定錯誤索引世代時，Runtime 維持未就緒並保留當前索引。對相同目標重複執行初始化時，既有索引、mapping 與 `_meta` 皆保留。
