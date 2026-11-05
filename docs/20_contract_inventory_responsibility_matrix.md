# 20 — Retrieval 契約、設定與責任總盤點

更新日期：2026-11-05。

本文件統整需要定義哪些契約、誰提供內容，以及 Library／Builder／Deploy 各自如何使用，作為 User、Component Developer 與平台開發者的閱讀入口。

**A～E 是契約群組，不代表只有五份 Schema 或五個檔案。**總表整理分類與責任邊界；資料精確定義引用既有契約，不重寫另一份。Descriptor／Manifest、完整 System Config／SDK、動態 UI 宣告的具體格式仍有待定事項。本次不修改 Prototype，也不表示相關後端功能已實作。

## 1. 先釐清 Builder DEV 與 FTEST／ENT

本文件的 **Builder DEV 指 Retrieval Builder 提供的開發／測試環境**，包含 Builder 前後端、用於測試的 Retrieval Runtime，以及可供選用的平台測試資源。它不只是前端網頁，也不是另新增一個使用單位的部署環境。

**FTEST／ENT 指使用單位匯出後的目標部署環境。**三者都適用 E 的環境與資源綁定，但管理邊界與使用方式不同。本文不推定公司內 FTEST／ENT 的完整名稱或環境等級。

| 名稱 | 本專案中的使用情境 | 設定與資源責任 |
|---|---|---|
| Builder DEV | User 在 Builder 設定與測試 System；上傳 CSV／JSON 或提出檢索問題，由 Builder 轉成 Runtime API 操作 | 平台提供測試 Runtime 與可選的測試 DB／模型 API；也可依權限綁定自備資源 |
| FTEST／ENT | 使用單位匯出 YAML，補齊環境設定並在自己的 K8s 部署 Runtime／必要服務；對外提供 API | 使用單位／部署者提供可用的 DB、模型 API、Endpoint、Secret 引用與部署資源 |
| Developer 本機開發環境 | Developer 以 SDK／範例開發、跑契約測試或自行啟動 Remote Service | 由 Developer 管理；本文件不以未加註的 DEV 指稱這個環境 |

使用同版邏輯 Config 時，D 可以沿用，E 依 Builder DEV、FTEST 或 ENT 分別綁定。換服務 URL／Secret 引用屬於 E；改 Component、切分長度、模型語意 Profile 或 Memory／MongoDB 模式屬於 D，不能在 Export 時偷偷改變。新環境的服務仍須滿足相同能力、Profile 與索引相容條件。

`DEV test use` 表示選用平台測試資源，不代表這些資源已交付到 FTEST／ENT。Export 需補齊目標環境的可用綁定；不預設匯出測試資料、索引內容或可用的真實 Secret。若 D 選擇 Memory，FTEST／ENT 也可以使用 Memory，但程序重啟後需重新 Ingestion；不強制改成持久化儲存。

## 2. 如何閱讀總表

### 2.1 人員與使用位置分開

- **Admin／平台開發者**：定義共用契約、SDK、登錄與部署規則；依權限管理資源。這是規劃／維護角色，不要求所有管理工作由一人完成。
- **Developer**：開發 Local Component 或 Remote Service；同一服務可能涵蓋單一或連續多個 Module。
- **Builder User**：在 Builder 建立與測試 System。若同一人自行部署或直接呼叫 API，也會承擔對應部署者／API 呼叫者責任。
- **Library**：可匯入的 Retrieval Engine Library，負責驗證、組裝與執行；本身不是已啟動的服務。
- **Builder**：Retrieval Builder 的 Frontend／Backend，管理設定、目錄呈現與 Builder DEV 測試；透過 Runtime 的目錄／驗證能力整合，不要求安裝所有 Local Component packages。
- **Deploy**：本表對「Export／部署交付與環境注入」的統稱，是使用階段，不是新 Module、獨立產品或第四種人員角色。Export 準備發生在 Builder，實際 FTEST／ENT 部署由使用單位進行；部署後仍由 Library／Runtime 執行。

### 2.2 格式、內容與執行資料分開

- **Schema**：驗證資料或描述的結構，例如 Chunk Schema、Descriptor Schema、Manifest Schema、System Config Schema。
- **Meta-schema**：規範 Schema 本身的寫法。Config Schema 採用 JSON Schema，平台另定支援範圍／必要限制；跨欄位、相容性與動態選項語意仍可能需要程式驗證。
- **Config／Descriptor／Manifest**：符合各自 Schema 的實際內容。Descriptor 內可以提供／引用 Config Schema；不能因此把所有 Admin 定義的格式都稱為 Meta-schema。
- **執行資料**：Chunk、QueryContext、IndexBinding 等實例由執行流程產生／使用。RunContext 提供資源與可信執行資訊，不等於 Component Config，也不等於 QueryContext。

**「—」表示沒有直接責任，不表示完全沒有間接關聯；「待定」表示尚需討論。**只列直接使用，避免因 User 在 UI 看到選項，就要求 User 編寫 Descriptor／Manifest。

## 3. 最終詳細總表

| 契約群組 | 包含的子項目與內容 | Admin／平台開發者制定 | Developer 閱讀／遵守 | Developer 交付 | Builder User 操作 | Library 使用 | Builder 使用 | Deploy 使用 | 關係與邊界 |
|---|---|---|---|---|---|---|---|---|---|
| **A. Engine 執行契約** | **資料**：IngestionDocument、ParsedDocument、Chunk、QueryContext、ResultSet 等。<br><br>**執行**：Module／連續區段 I/O、Local 執行介面、Context。<br><br>**索引**：IndexBinding、Artifact Definition。 | 共用資料 Schema、I/O 語意、SDK 執行介面、Context 取得規則；Artifact Definition 格式及相容性規則。 | 自己涵蓋區段的 I/O 與語意。<br><br>**Local**：另看 SDK 介面／必要的 Context 用法。<br><br>**涉及索引**：另看 Binding 與支援的格式。 | 符合契約的實作、輸入輸出範例、契約測試。<br><br>**引入新／未註冊索引格式時**：提供 Artifact Definition（target Schema、讀寫語意、能力限制）及相容 Retrieval／Adapter；沿用已註冊格式則宣告支援。 | — | 執行並傳遞資料、提供 Context、驗證 I/O 與索引相容性。 | 使用測試 API 對外的輸入／輸出格式；不承擔所有內部 SDK 介面。 | — | **B／C 引用 A。**跨 Module 的 Component 遵守核定區段邊界，不強迫回傳所有中間物件。<br><br>IndexBinding 是執行資料；Artifact Definition 是可共用的索引格式規格，屬 A 的擴充規格，不必每個 Component 各寫一份。 |
| **B. Component 定義** | **Descriptor**：識別、版本、涵蓋範圍、I/O 引用、能力、相依與資源需求。<br><br>**Config Schema**：參數、型別、預設值、限制。<br><br>**UI 宣告**：提示、動態選項、相依規則，具體格式待定。 | Descriptor Schema；Config Schema 採用規範與支援範圍／必要的 Meta-schema 或驗證規則。<br><br>UI 宣告格式另行討論。 | Descriptor 必要資訊、參數 Schema 規範、能力與資源宣告方式。 | **Local**：Component 宣告、Config Schema、能力／資源需求，可由 SDK 根據程式定義產生。<br><br>**Remote**：相關資訊以 C 為來源，由平台推導／適配成目錄描述，避免手寫兩份。 | — | 驗證參數與能力，經 Registry 取得 Local 實作或 Remote Adapter。 | 顯示 Component 選項，產生表單與相依提示；真實 Registry／動態規則整合尚待實作。 | — | **B 的規格供 D 選用；Config Schema 驗證 D 的參數值。**<br><br>Local class／factory 接線由 Registry／SDK 管理；共用 Descriptor 是否需額外接線欄位、正式來源與版本格式仍待定。 |
| **C. Remote Service 定義** | **Manifest**：服務識別、operations、參數、呼叫資訊、部署／連線需求。<br><br>**Image 分支**：image、啟動／部署描述。<br><br>**External 分支**：既有服務連線及認證綁定需求。 | Manifest Schema、operation 規則、Remote HTTP 請求／回應／參數協定、Image／External 必要資訊；具體格式待定。 | **Remote Developer 才需閱讀**：Manifest、呼叫協定與 operation 的 A 邊界契約；依部署模式看對應交付規格。 | Manifest、可呼叫的服務、API 範例與契約測試。<br><br>**Image**：另附 image 與啟動／部署資訊。<br><br>**External**：由 Developer 部署，交接可用服務及環境連線資訊；環境實際值歸 E。 | — | Adapter 依 operation 呼叫服務，驗證並轉交符合 A 的業務資料。 | 登錄服務、推導 B 的選項；管理 Builder DEV 測試所需的服務啟動或連線。 | **Image**：產生／使用服務部署設定。<br><br>**External**：只綁定既有服務，不部署該服務。 | **operation 導出 B，I/O 遵守 A，環境需求由 E 滿足。**兩種 Remote 模式都可有多個 operation；一個 operation 可涵蓋連續多 Module。<br><br>僅宣告平台需提供／部署／驗證的依賴；Developer 內部自行管理的服務不必全部公開。 |
| **D. System 組裝設定** | **System Config**：Component 選用、參數值、流程與結果處理設定、資源引用。<br><br>**System Document Schema**：業務欄位與 metadata 規格；目前語意見 05，正式包裝／格式待定。 | System Config Schema、組裝與相容性規則；Document Schema 定義格式與驗證責任。 | 整合範例時，閱讀 Component 選用、參數與資源引用方式。 | 可執行的整合範例 Config 與測資，展示如何接上前後段；正式 SDK 未交付前，現有示例須標註草案／離線範例。 | **主要操作位置**：選 Component、填參數、設定流程與資料欄位。 | 解析 Config、取得 B／C 定義，驗證後組裝並執行 System。 | 編輯、驗證、儲存與測試 Config，呈現設定錯誤。 | 將 Config 提供給目標 Runtime。 | **D 保存 System 的邏輯組裝結果**，引用 B／必要的 C，搭配 E 執行。<br><br>不把 Descriptor、Manifest 或 Live Client 全部複製進 D；邏輯資源引用與環境實際值分開。 |
| **E. 環境與資源綁定** | Builder DEV／FTEST／ENT 的 Endpoint、Secret 引用、DB／實體索引目標、儲存與部署資源設定。<br><br>涵蓋平台測試資源、自備 DB／模型 API 與 Remote Service 的環境值。 | 環境綁定 Schema、資源類型、Secret 引用、部署／驗證規則；管理平台可提供的資源。 | **需要平台資源或協助部署時**，閱讀綁定與部署規格。 | 必要的綁定範例及部署／連線交接資訊。<br><br>資源「需求」已寫在 B／C，E 示範如何滿足，不重複定義需求。 | 選用資源；自備資源或兼任部署者時補設定。 | 解析綁定、初始化 Client 等資源，透過 A 的 Context 提供。 | 提供 Builder DEV 資源選擇與必要設定介面。 | 注入連線、Secret 引用、儲存及部署資源。 | **E 滿足 B／C 需求，與 D 一起建立可執行 System。**<br><br>同版 D 可搭配不同 E，但需相同邏輯能力。Live Client／索引物件留在 Runtime 程序中，由 Engine 管理生命週期。 |

上表 A～E 的內容可分別存在程式定義、JSON Schema、登錄資料或設定檔；**交付內容不等於要求 Developer 手寫多份 JSON**。SDK 可產出設定 Schema／Descriptor，Remote 可由 Manifest 推導目錄資訊。精確包裝與來源規則待正式介面核定。

## 4. 上下關係與容易混淆的邊界

### 4.1 B 的參數規格與 D 的實際設定

Developer 在 B 定義 `chunk_size` 為正整數、預設 512。User 在 D 選用這個 Component 並填入 256；另一個 System 可填 1024。兩者共用 B，分別保存自己的 D；修改一個 System 不改變其他 System 或 Component 規格。

Config Schema 是 B 的內含／引用規格，Component Config 是 D 的子內容，兩者不另列為第六個契約群組。由 Library 驗證有效設定，Builder 的 UI 驗證不能取代 Engine 的驗證。

### 4.2 A 的 IndexBinding 與 Artifact Definition

Indexing 提供該 System 的 IndexBinding，Engine 驗證、管理，Retrieval 經 Context 取得。一般 User 不編寫 Binding。Artifact Definition 說明索引格式、target 形狀與讀寫語意；Binding 本身不能取代這份規格。

第一版每 System 一組邏輯索引，不新增 index_ref 或 searchable；Runtime 管理就緒狀態。Artifact Definition 可被多個 Indexing／Retrieval 共用；新／未註冊格式需註冊，相同既有格式只需宣告支援。精確定義沿用 [19](19_index_binding_artifact_contract.md)。

### 4.3 C 的服務、operation 與 B 的選項

例如同一服務提供一個處理 Parsing～Embedding 的 operation，及另一個執行 Retrieval 的 operation。Image／External 都可能有這種情境；operation 不等於 Module，也不代表每個 operation 都要一個 Pod。

Manifest 供平台建立可選的 Component 描述；User 在 D 選用，Library 的 Adapter 依服務操作規格呼叫。固定設定的 External Service 可以沒有可調參數，UI 顯示固定能力與限制；若目錄需要 Config Schema，以合法空物件 Schema 表達即可。

延續 [18](18_remote_service_pipeline_integration.md)：Remote Image 第一版每 System 使用獨立服務實例／必要資料綁定；External 由 Developer 維運，沿用既有資料空間，多個 System 可能共用資料。第一版不加入 data_space_id 或 shared 開關。

### 4.4 涵蓋範圍與執行模式是兩個維度

Local／Remote 是執行模式；單 Module／連續多 Module 是涵蓋範圍。Remote 連續多 Module 方向已在 18 確認；本輪盤點亦納入 Local 跨 Module 的需求，正式區段執行介面與 Descriptor 表達仍待定，不能直接把單 Module Parser ABC 當成任意區段介面。

擬議第一版同一 Pipeline 內以連續區段處理，依核定的邊界型別交接；不在本次新增任意 DAG、不連續範圍或跨 Ingestion／Inference 的單次操作格式。

### 4.5 Document Schema 與動態 UI 選項

System Document Schema 屬 D 的資料規格；既有 05 約定以 ParsedDocument 的 Unit 欄位／文件 metadata 為對象，解析後驗證，原始輸入另由 IngestionDocument 與 Parser 規格檢查。正式定義格式、映射／錯誤定位細節仍待對齊，不把每種 Parser 的任意輸入都當成同一欄位表。

「Embedding 設定產出哪些向量，Indexing 才能選哪些向量」是另一項動態候選與相依需求，預計由 B 的宣告配合 D 當前設定解析。候選值應是向量的輸出名稱，不一定等於原始來源欄位名稱。

**動態 UI 的 Schema／Meta-schema 本輪暫緩討論。**[12](12_component_schema_ui_contract.md) 中的 option_sources、UI hints、規則與範例均仍是草案，不能因總表使用這些概念就視為格式定案。解析候選只需可序列化的設定／能力資訊，不把 Live Client 或完整 RunContext 傳入瀏覽器。

## 5. Developer 依開發模式閱讀與交付

1. **Local Component**：從 [11 開發指南](11_component_developer_guide.md) 閱讀 SDK 規劃，接著看 A 中涵蓋範圍的 I/O 與資料契約，再看 B 的設定／能力宣告。交付實作、宣告、測試及 D 的範例；需要資源才補 E。
2. **Remote External Service**：看 A 的業務邊界與 C 的服務協定規劃，交付服務、Manifest、測試、D 的範例及必要的 E 連線交接。服務內部語言／框架自行選擇，不強制繼承 Local ABC 或採用 FastAPI；既有 API 不符契約時仍須適配。
3. **Remote Image Service**：在上述 Remote 內容上，另交付 image、啟動／健康檢查／設定注入／必要資源與儲存綁定資訊，供 Builder DEV 管理及目標環境部署。精確必要欄位留 C 的 Schema 討論。
4. **新增索引格式**：額外閱讀 [19](19_index_binding_artifact_contract.md)，交付 Artifact Definition 及可相容讀取的 Retrieval／Adapter；沿用格式則引用既有定義。

Parser 的具體教學入口是 [16](16_parser_component_development_examples.md)，涵蓋 IngestionDocument → ParsedDocument、Local ABC 與 Remote API 示範。它是可執行的教學範例，不等於正式 SDK／完整 Remote 協定已發布。

上述精簡閱讀路線保留 [11 的交付要求](11_component_developer_guide.md)：除了程式與 Schema，還需按適用範圍說明版本相容、能力／資源、維護者、變更影響、範例及測試。選填的 _rag 追溯不因這張表變成強制實作。

## 6. 既有規格位置與待定事項

### 6.1 精確定義的閱讀入口

- **A**：[04 Module I/O](04_module_components_io_contracts.md)、[13 IngestionDocument](13_ingestion_parser_input_contract.md)、[14 ParsedDocument](14_parsed_document_contract.md)、[15 Chunk](15_chunk_contract.md)、[17 Pydantic 範例](17_pydantic_contracts_draft.md)、[19 IndexBinding／Artifact](19_index_binding_artifact_contract.md)。Inference 沿用 QueryContext[]，不恢復 InferenceState wrapper。
- **B**：[11 開發指南](11_component_developer_guide.md)、[12 設定描述草案](12_component_schema_ui_contract.md)。
- **C**：[18 Remote Service／Pipeline](18_remote_service_pipeline_integration.md)、[16 Parser 開發範例](16_parser_component_development_examples.md)。
- **D**：[05 資料／Config](05_data_contracts_search_design.md)、[06 UI 規格](06_ui_development_spec.md)。
- **E**：[03 正式名詞與環境邊界](../03_architecture_proposal.md)、[07 Backend／Runtime／Export](07_backend_runtime_integration.md)、[18 Remote 部署](18_remote_service_pipeline_integration.md)。

### 6.2 此次盤點未直接定案的內容

- **A**：正式 SDK／Context 介面、Local 跨 Module 區段介面、索引實體布局與 Artifact Definition 完整機器格式；追蹤 Q-002／Q-011／Q-013／Q-028。
- **B**：統一涵蓋範圍、Descriptor 精確欄位、Local Registry 接線／Remote 推導規則。動態 UI Meta-schema 特別保留待討論；追蹤 Q-002／Q-022／Q-028。
- **C**：Manifest 的 Image／External 必填與選填欄位、HTTP Envelope／錯誤／參數傳遞、版本及註冊管理；追蹤 Q-019／Q-021／Q-028。
- **D**：完整 System Config／Document Schema 定義格式、引用與版本包裝、動態相容性驗證；追蹤 Q-002／Q-015。
- **E**：綁定實體格式、資源／Secret 管理與部署生命週期；追蹤 Q-017／Q-020／Q-021。

決策狀態由 [08](08_implementation_plan.md) 維護。本次總盤點沒有將整個 Q-ID 關閉，也未新增 UI 實作承諾。後續若核定具體 UI 變更，仍先記入 [10 UI Backlog](10_ui_adjustment_backlog.md)，收到改 UI 指示後再實作。


## 7. 2026-11-05 已確認補充：版本、登錄與 Runtime 控制

- **A**：同 System／document_id 完整覆寫，文件級成功／失敗；成功發布新版、失敗保留最後成功版本，不續跑半份資料。具體提交／Remote 崩潰一致性仍須實作驗證。
- **B／C**：Component 有實作版本，System 固定選用、不自動升級；Admin 手動審核登錄／發布。Local 須在目標 Runtime 有程式／依賴；Remote 須有相容 Adapter／操作邊界與可用服務。動態 UI Meta-schema 仍暫緩，不因確認管理方式而凍結 Descriptor／Manifest。
- **D／E**：D 保存流程／參數／版本選用；E 保存 Queue／併發／Rate／Deadline 等環境控制值。Builder DEV 與獨立 Runtime 共用控制實作，Builder 可另設 User／Workspace 平台配額。
- **Runtime 管理資料**：有上限 Queue，文件執行併發預設 1 可調；同文件 queued／running 拒絕重複提交。202 後提供 run_id／document_id 查詢，文件最新狀態另存記憶體，不改共用業務 DTO。
- **重啟政策**：不保留／恢復 Queue／Run／文件狀態；無紀錄查 unknown，不由已儲存文件推定最近一次完成。索引持久化／Remote 副作用與工作紀錄分開看待。

上述方向記 D-56；[21 API 盤點](21_runtime_ingestion_inference_api_inventory.md) 列出 5 支業務＋2 支 Health 的建議最小清單及 API-D01～06。API 路徑、Batch 包裝／接收、Run partial、HTTP／錯誤及數值上限仍待核定；不是新增五個已實作的契約或已發布 API。
