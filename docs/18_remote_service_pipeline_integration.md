# 18 — Remote Service／Pipeline 註冊與部署

2026-11-02｜已確認的產品方向與整合規劃。Manifest 正式 Schema、HTTP 傳參、SDK／部署控制介面尚待核定；本文件不代表相關後端功能已實作。2026-11-03 Prototype v0.12 已加入模擬目錄／表單／鎖定／Export；Inference 邊界同步 D-54 的 QueryContext[]。

## 1. 要解決的情境

Developer 可能不提供原始碼，而是交付既有 API 或 Image；既有系統也可能一次完成多個 Module，不願拆成多個可獨立呼叫的 Component。

| 整合單位 | 行為 | Developer 交付 |
|---|---|---|
| Local Component | 在 Library／Runtime 程序內執行單一 Module | 原始碼、契約／設定描述及測試 |
| Remote Component | 一次 API 呼叫完成單一 Module | Service Manifest＋Image 部署描述或既有端點綁定 |
| Remote Pipeline | 一次 API 呼叫承接同一 Pipeline 內連續多個 Module | 一份服務宣告及該段邊界 Contract，不必逐 Module 實作 Component ABC／端點 |

三種交付模式仍是 Local、Remote Image、Remote External Endpoint；Remote Pipeline 是涵蓋範圍，不是第四種部署模式。單一 Service 可同時註冊多個單 Module 端點，也可提供整段端點；前者仍分別接線，後者只呼叫一次。第一版不支援以單次遠端呼叫替換不連續的 Module，也不因此開放任意 DAG。

## 2. 整段的輸入輸出與組裝

常見例子：文件處理服務承接 **Parsing → Chunking → Embedding**。

| 項目 | 約定 |
|---|---|
| 輸入 | Import 驗證後、與 API 相同 Schema 的 IngestionDocument |
| 遠端內部 | 自行完成解析、切分與向量化，不要求回傳中間 ParsedDocument |
| 輸出 | 符合 15 的 Chunk[]，包含合法來源／版本、fields、metadata 及命名 vectors |
| 平台後續 | 以相容 Indexing 接收 Chunk[] |

不新增另一份文件／Chunk 型別。Remote Pipeline 的最終輸出仍需滿足其涵蓋步驟的對外語意，例如 metadata 繼承、必要識別與向量 Profile／來源／維度；_rag 追溯為選用，有提供才驗證；不要求暴露私有中間物件。精確批次包裝、部分成功與來源識別驗證方式仍待 Contract 核定。

Engine 依核可服務宣告編譯執行計畫，驗證涵蓋範圍連續、邊界 Contract／能力相容、不與其他選擇重疊；被接管的本地 Module 不再執行。Remote 呼叫失敗時不靜默改跑本地演算法。多 Parser／路由等情境須明確宣告作用範圍，第一版不能同時啟用重疊的替換範圍。

若涵蓋 Indexing，必須宣告索引的存取方式、Profile／版本能力與相容 Retrieval，Builder／Engine 共同卡控；不能只看回應 JSON 相同就接任意 Retriever。完整外部系統可在同一 Service 註冊 Ingestion 與 Retrieval 兩段能力，綁定一致的服務／資料設定。具體索引回應、成對綁定及 HTTP 格式仍待 Q-002／Q-015／Q-019；本次不凍結 17 的 IndexBinding 提案；Rerank Input／Output 統一使用 D-54 QueryContext[]。

## 3. Service Manifest 與註冊流程

Developer 提供 Manifest，平台管理者審核並註冊；Builder User 在選單選服務，不自行填寫這些 Developer Service 的 URL、API Path 或 Header。平台提供共用 Remote API Adapter；服務符合支援的協定及邊界 Contract 時，Developer 不必另寫每個 Module 的本地 Component。既有 API 不符時仍需適配程式，不能靠 Manifest 自動轉換任意 Payload。

以下是需描述的資訊群，**不是已定案的欄位拼字或完整 Manifest Schema**：

| 資訊群 | 內容／例子 |
|---|---|
| 識別與顯示 | 穩定服務 ID、版本、名稱、說明、維護者 |
| 執行範圍 | 單 Module 或連續範圍，例如 Parsing～Embedding；一份服務可宣告多個操作 |
| Contract／能力 | 輸入輸出引用及版本、向量／索引能力、requires／provides、相容 Engine／Adapter |
| 可設定參數 | 可選的 Config Schema、UI hints、相依規則、預設值與限制 |
| 呼叫描述 | 操作端點的相對 Path／Method、序列化協定、Timeout、認證需求；不包含 Secret 值 |
| Image 部署描述 | Image 版本引用、Port、健康檢查、資源需求、設定檔／Secret 注入、外部依賴 |
| 外部端點綁定需求 | 所需的連線與認證引用，由 Developer／管理者按環境設定 |
| 驗收與變更影響 | 輸入輸出、失敗案例、契約測試、固定設定／版本、重新 Ingestion／索引相容影響 |

註冊流程：提交宣告與材料 → 審核 Manifest／Contract／Adapter 能力 → 加入核可目錄 → Builder 顯示 → 選擇與驗證 → 解析部署綁定。只有 Manifest 不足以保證服務可執行；目標 Runtime 必須支援該 Adapter、範圍與協定。未部署、連線失敗或版本不相容需顯示原因，不把「已註冊」當作「已 Ready」。不開發專用的 Service UI 或任意前端腳本。

## 4. 三類設定與固定服務

| 類別 | 提供者 | 保存／傳遞 |
|---|---|---|
| 服務定義 | Developer，經平台核可 | Manifest；描述能力、可調整項目與部署需求 |
| System 邏輯 Config | Builder User | 選定服務／版本、範圍及開放的演算法參數 |
| 環境綁定 | Developer／平台管理者／部署者 | DEV／FTEST／ENT 的 Endpoint、Secret 引用、儲存目標及資源 |

模型語意、Chunk 長度等即使透過啟動設定檔載入，仍屬邏輯參數，不因傳遞方式而變成環境覆寫。Image 模式由邏輯 Config 與環境綁定渲染設定檔，第一版修改啟動設定後重新部署，不承諾熱更新。

Developer 自行部署且已固定設定的服務，可不提供使用者可填的 Config Schema；UI 只顯示能力／固定值與限制，不出空白參數表單。既有 12 的單 Component Descriptor 若需要 config_schema，Adapter 以合法空物件 Schema 表示無可調參數，不要求重寫原服務。固定服務的模型／索引等語意應隨註冊版本記錄；不因使用者未填參數就假定跨環境相容，Endpoint 背後語意改變需重驗證並記錄變更。

若 API 明確支援每次呼叫的功能參數，才由 Manifest 宣告並在 UI 展開；精確參數 Envelope／Header 協定待 Q-019 核定。不把任意演算法／連線設定塞進文件 metadata、借用 parsing_profile 或傳送整個可信 RunContext／Config／Secret；D-52 允許 Component 明確支援的文件層提示（如 chunking_mode），不是任意 Config／授權覆寫。16 的無參數 Parser HTTP 範例維持原 body。

## 5. 執行實例、儲存與資料共用

System 是 Library＋Config 建立的邏輯實例，不等於 Pod。Service 是運算／API 邊界，也不等於 Persistent Layer。

| 模式 | DEV 第一版 | 資料責任 |
|---|---|---|
| Local | 同一程序／Pod 可載入多份 Config 建立多個 System；不強制每 System 起 Pod | 每 System 設定、執行狀態及索引作用範圍分開；資源共用與限制由 Engine 管理 |
| Remote Image | 每 System 啟動獨立 Service 實例；整段 Pipeline 共用該實例，不逐 Module 起 Pod | 需要儲存時，以啟動綁定配置獨立 Collection／Index／Volume 等範圍；不開放跨 System 共用設定 |
| Remote External Endpoint | Developer 自行部署維運，平台不建立／重啟該服務 | 固定使用服務既有資料空間；多 System 選同一服務可能共用資料，平台不承諾自動隔離 |

**第一版不加入 data_space_id，也不設 shared 開關或每次請求切換資料空間。**未來需要時另案擴充，不改寫目前共用資料 Contract。無狀態 Parser 等服務不需要資料空間設定。

不同 Pod 不會自動隔離資料；Image 服務若需要可指定的儲存目標，Developer 必須提供啟動綁定能力。無法配置獨立儲存範圍的 Image，不可宣稱符合此模式的多 System 獨立部署要求。ES／MongoDB 伺服器可共用，但須綁定各 System 的獨立儲存範圍。

## 6. DEV 啟動與 Export

Image 模式：使用者選服務並填開放參數 → 儲存／套用設定 → Builder Backend 協調開發環境部署機制，依宣告建立 Deployment／Service 及設定／Secret 引用 → 等待健康檢查 → 自動取得內部 Endpoint → Runtime 解析綁定。就緒前阻止相依操作；初始化失敗需回報服務／範圍與原因。建立、更新、停止／刪除及資源清理由平台管理，具體控制器／API／狀態枚舉留 Q-017／Q-020／Q-021。

External 模式：Developer／管理者登錄 DEV 連線與 Secret 引用 → 驗證契約／連線 → Runtime 呼叫；不擅自重部署外部 Service。一般 Builder User 不填 API 連線；目標環境綁定由部署責任者補齊。既有 LLM／Embedding API、ES 等 BYO 資源的設定流程保留，不把它們一律改為本文件的 Developer Service 註冊。

| 模式 | FTEST／ENT Export |
|---|---|
| Local | Runtime Image 引用＋Config＋環境綁定；程式已在 Image |
| Remote Image | 上述內容＋Remote Image 引用及 Deployment／Service／資源／設定檔／Secret 引用 YAML |
| Remote External Endpoint | Runtime＋Config＋目標環境連線／Secret 引用；不輸出遠端服務部署 YAML |

Export 不搬移 Image 本體、真實 Secret、原始文件、Chunk／vectors 或外部 DB；目標環境需取得 Image 並準備依賴／資料。DEV 的暫時 URL 不直接當作 FTEST／ENT 綁定。沿用同版服務語意、邏輯參數與涵蓋範圍，不能換成不同模型或不同演算法卻當作純 URL 覆寫。

## 7. UI 與驗收

第一個 Module 是整段的選擇入口；例如 Parsing 選「文件處理 Pipeline」，顯示 Parsing～Embedding、邊界 Contract 與可調參數。Chunking／Embedding 保持可見，標示「由 XXX Pipeline 管理」並鎖定獨立設定；Indexing 正常設定。底層以一筆整段綁定編譯，不把整段藏成 Parser 私有設定。切回本地選擇後重新驗證，不能把殘留草稿加入有效計畫。

驗收至少包含：連續範圍／重疊卡控、相容索引讀寫配對、輸出語意、只執行一次、固定服務無參數表單、失效服務引用保留並定位、Image 實例與資料分離、External 固定資料提示、健康／失敗與清理、兩種 Export 內容差異。不得拿 Mock 當真實部署證據。Trace 預設記整段呼叫的耗時／結果；中間 Module 診斷為選配，不保證各步可單獨替換或計分。

UI 模擬流程已實作，真實服務管理尚未實作，見 [10 UIB-016](10_ui_adjustment_backlog.md#uib-016-remote-service-pipeline)。開發計畫與未決細節見 [08 D-51／Q-028](08_implementation_plan.md#q-028)，設定描述沿用 [12](12_component_schema_ui_contract.md)，部署責任見 [07](07_backend_runtime_integration.md#remote-service-deployment)。



## 8. 推論整段邊界與原型限制（D-54）

同一推論 Pipeline 內的 Remote 單 Module／整段都接收、回傳 QueryContext[]，沿用 filters／metadata 與目前有效結果。Config／Secret／可信 ACL 不放在這個 body。ResultSet.key 為穩定路徑／群組；多個 context 可以保留，不為了 HTTP 再融合。HTTP 版本／參數 Envelope 仍待 Q-019；舊 InferenceState body 須明確升級，不靜默混用。

v0.12 的 Service Manifest／健康狀態／Image／Endpoint／資料綁定僅為固定示例，沒有真實 Pod／服務／獨立儲存。Export 的兩種差異可展示，尚不是可直接部署的交付物。詳細完成／待辦分界見 10。
