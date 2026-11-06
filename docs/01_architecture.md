# Retrieval Builder：架構、名詞與責任

## 閱讀目錄

- [產品目的與現行範圍](#產品目的與現行範圍)
- [系統組成與管理階層](#src-03-31-系統組成與管理階層)
- [模組與處理流程](#src-03-32-模組與處理流程)
- [Config 與部署設定](#src-03-33-config-與部署設定)
- [版本概念](#src-03-34-版本概念)
- [元件關係與實作責任](#src-03-35-元件關係與實作責任)
- [A～E 契約與角色責任總表](#src-20-3-最終詳細總表)
- [使用流程與圖面解讀](#src-03-4-使用流程與執行入口)
- [歷史名稱與遷移對照](#src-03-38-component-命名統一2026-10-29d-43)
- [主責與一致性規則](#主責與一致性規則)


更新：2026-11-05。本手冊維護產品範圍、名詞與 A～E 責任；具體資料、Component、設定、API、UI 與開發狀態分別由其他七份手冊維護。唯一入口為 [README](../README.md)。

## 產品目的與現行範圍

Retrieval Builder 協助 User 建立、測試與匯出 Retrieval System，提供合理預設、CSV 測試與 AI 設定助手。Library＋Config＋必要資源綁定構成具體 System；同一 Runtime／共用 Flow 可服務多份 System 設定。

- Retrieval-only，沒有 Generation；Rewrite／AI 助手仍可使用 LLM，Evaluation 保留 M6。
- UI 是 Workspace／Group 與 System 卡片、單一 Create／Edit，提供 Ingest／Inference／Evaluation／Export。
- 可先設定再上傳資料，也可先提供 CSV，由 AI 助手建議設定；建議與手動操作使用同一驗證。
- 原型現行為 v0.12，僅瀏覽器模擬。後續規格先寫文件，UI 變更列 Backlog，明確要求改 UI 時才做。
- M4 先交付可獨立使用的 AI 設定助手，M5 再完成 Builder 與助手整合；其餘 M0～M7 以計畫手冊為準。

<a id="system-terms"></a>

<a id="src-03-31-系統組成與管理階層"></a>
## 系統組成與管理階層

| 名詞 | 定義 |
|---|---|
| Retrieval Builder | 設定、管理、測試與匯出 Retrieval System 的開發平台；含 Frontend／Backend |
| Workspace | Builder 中管理 System 的容器；正式階層為 Workspace → System |
| Retrieval Engine Library | 可匯入的程式庫，提供 SDK 契約、Registry、Config 驗證、模組組裝與執行核心；本身不是已啟動服務，也不是某一個 System |
| Retrieval Engine Platform | 共用執行技術堆疊，包含 Library、Runtime API 封裝及共用 Runtime Image；不是 Builder 的別名，也不是 Runtime 每次執行必須呼叫的中央服務 |
| Retrieval Runtime | 載入 Library／Registry 與服務基礎設定，提供 Ingest／Query／文件管理／Health API；Builder 共用模式管理多個 System／Config，獨立模式啟動時綁定單一 System Config |
| Retrieval System | Library 依特定 Config 組裝，並完成必要服務及資料／索引綁定後建立的具體檢索系統；可由 Python 直接使用，也可由 Runtime 對外提供 API |
| Retrieval Service（圖面用語） | Runtime 內的 System 執行實例；不是新的管理層級、必要微服務或 Kubernetes Service 物件 |
| AI 設定助手 | 依需求、樣本、可用方法及 Config Schema 產生設定草稿的能力；可獨立由 Python／API 使用，Builder 另外提供互動、差異預覽及套用介面，不是 Ingestion／Inference 的必經模組 |
| Evaluation Runner | 批次執行 Dataset 與收集指標；重用 04 的評估邏輯，由 Runtime API／部署手冊 管理任務與儲存 |

核心關係是 **Retrieval Engine Library ＋ Config → Retrieval System**；實際執行還需解析必要的資源／服務綁定。Python 使用者可直接載入 Library 建立 System，不需要 HTTP 或 Builder。Platform 將 Library 與 Runtime API 打包為共用 Image，部署時再載入 Config／環境設定，無須每份 Config 重新建 Image。

Builder 管理設定與測試，Library 執行模組，Platform 交付執行框架，Runtime 承載 API，System 是依 Config 建立的具體應用。System 不等於 Pod／程序；Builder Local 共用 Runtime 指同一 API service／程序內建立多個 System，不只是共用 Pod，各自保有設定與資料作用範圍，資源限制與生命週期細節仍見 Q-017／Q-020。Remote Image 第一版每 System 獨立服務實例；External Endpoint 由 Developer 自行部署。 重啟 API service 程序即使不重建 Pod，仍影響該程序內所有 System 的 Memory 資料／工作；D-62 採共用 Flow／Executor，Builder Config 更新以新版配置快照及必要資源準備生效，不要求重建每份 Config 的專屬 Flow，也不必逐 Config 重啟共用 API service；D-63 確認該 System 的 Ingestion 結束後才允許新版設定生效；資源回收細節待定，模式對照見下一節。

<a id="runtime-deployment-modes"></a>

<a id="src-03-311-builder-共用與-ftestent-獨立模式d-61d-62"></a>
### Builder 共用與 FTEST／ENT 獨立模式（D-61／D-62）

| 環境 | Config 與 API service 的對應 | API service 啟動時 | Config 更新 |
|---|---|---|---|
| Builder DEV | UI 保存多份 System Config，共用一組或少數幾組 API service；每組均提供 Ingestion＋Inference，不逐張卡建立服務 | 載入 Library／Registry、服務／資源基礎設定，不被單一 System Config 定型；透過可信管理取得各 System Config | 驗證新版 Config 快照及相依資源，後續請求由共用 Executor 選 Component；不要求重建專屬 Flow；有 queued／running Ingestion 時僅存草稿，工作結束後才允許套用，資源切換仍待細化 |
| FTEST／ENT | 主 Runtime 第一版基準為一個 Pod＋一組 API service＋一份 System Config | 綁定該 Config 與環境資源，建立該 System 實例，業務請求不另選 System | 以重啟／重新部署該 API service 採用新 Config；資料／索引相容與需否重新 Ingestion 仍需驗證 |

Builder Backend 下發／註冊 Config 與目標 Runtime 的對應，Runtime 依可信 System 識別取得已驗證 Config 快照，由共用 Flow／Executor 執行；各 Module 解析所選 Component 並傳入該次 Config／Context，Library 不直接讀 Builder DB。服務啟動不綁單份 Config，不代表 Engine／已安裝 Component 版本可任意熱替換；新增 Local 程式仍按原 Image／版本交付流程。

少數共用服務可以依 Namespace／資源池等方式分組，但分組單位、數量與管理機制待決；不將 Namespace 與 Workspace／System 當成同一概念，也不新增 User 必填分組設定。Config 解析結果、Component 實例與資源可按需求快取；精確預載、LRU／回收與配額依 Q-020。共用 Flow 不要求共用所有 Component 實例，保存多份 Config 也不等於同時初始化所有模型／索引。每次請求／已接收文件固定使用同一 Config 快照，不在執行到各步時重新讀取最新版；D-63：該 System 有 queued／running Ingestion 時可保存草稿，暫不啟用新版；既有工作結束後才允許套用。其他 System 不受影響，不新增 Query 讀寫鎖；舊 Query 資源回收與 Remote 結果不明的判定仍待細化。

FTEST／ENT 的一 Pod 基準指主 Runtime。若 Config 選 Remote Image，仍依 D-51 部署必要的遠端 Component service；External 由 Developer 維運，不因此承諾整套系統永遠只用一個 Pod。Ingestion／Inference 是同組 Runtime 的 API 能力，不強制各自一個 Pod／程序。

**範圍：Retrieval-only，不提供 Generation。** Inference 回傳排序後的檢索結果、分數與來源／追溯資訊，由呼叫端決定如何消費。Query Rewrite／Multi-query 與 AI 設定助手仍可使用 LLM；取消 Generation 不等於移除所有 LLM。

<a id="pipeline-terms"></a>

<a id="src-03-32-模組與處理流程"></a>
## 模組與處理流程

| 名詞 | 定義 |
|---|---|
| Module（模組） | Pipeline 中的功能分類與契約，定義職責、Input／Output 及語意，例如 Parsing、Chunking、Retrieval、Rerank |
| Component（元件） | 遵守某個 Module 契約、可註冊及選用的具體實作，例如 Chunking 的 FixedSizeChunker／RecursiveChunker；包含參數描述、相依能力與執行邏輯 |
| Component Instance（元件實例） | Component 的執行物件；每次執行接收本次參數及 Context。無狀態且可安全併行者可共用，有狀態或綁定特定資源者可依 System／資源分開，不要求每份 Config 各有一份實例 |
| Pipeline（處理流程） | Module 及其執行規則組成的流程；本產品採固定骨架，依 Config 選擇 Component、參數及核定的組合策略 |
| Ingestion | 將輸入資料經 Import、Parsing、Chunking、Embedding、Indexing 處理，準備可供查詢的資料／索引 |
| Inference | 接收問題，執行 Query Transformation、Retrieval、依配置進行 Fusion／Rerank，回傳最終排序的檢索結果 |

Module／Component 是職責與選擇層次，不以 Python Class 或 Function 的實作形式區分；實作及 I/O Contract 見 [Engine／Component 開發](03_engine_and_components.md)。Ingestion 與 Inference 透過資料／索引綁定銜接，不要求每次提問都重新 Ingestion。純全文模式略過 Embedding、None 的 pass-through，以及 Fusion 的合併時點等執行規則見 [架構與責任相關章節](#src-03-31-系統組成與管理階層)／Engine手冊；本節不增加通用 DAG 編輯器。

各 Module 規劃提供內建 Components，Module Developer 也可加入遵循相同契約、設定描述與相依要求的 Component。內建／自訂元件經同一 Registry 管理，使用者在 Builder 選用目標 Runtime 實際包含且核可的元件；預設提供不等於全部同時執行。[Library／Config／System 示意圖](../diagrams/03_module_component_concept.png) 上半部保留完整 Library 的 Module／Component 目錄與 Developer 交付流程，逐項呈現既有內建／自訂選項，並於 8 個 Module 各增 Remote API Component。Chunking 額外列出 Developer 在 Library 開發的 XXX_component。下半部以同一 Library 配三份 Config 建立 System：A 全部選內建，B 的 Chunking 選 XXX_component（Local），C 的 Parsing 選 Remote API Component 並連到獨立 Parsing Service。各 System 展開 Ingestion Service 的 Import／Parsing／Chunking／Embedding／Indexing，以及 Retrieval Service 的 Query Transformation／Retrieval／Rerank；實例名稱附 A／B／C。URL／Secret／Image 由部署設定綁定。詳細說明見 [架構與責任：圖說](#src-03-31-系統組成與管理階層)。Service 是邏輯邊界，不強制拆 Pod；圖中目錄及示例是目標設計，不是已交付清單。

<a id="config-terms"></a>

<a id="src-03-33-config-與部署設定"></a>
## Config 與部署設定

| 名詞 | 定義 |
|---|---|
| Config | System 的邏輯處理設定，包含 Module 的 Component／參數，以及 Pipeline、資料欄位相關參數、Prompt、模型語意 Profile 與邏輯服務引用；I/O 資料細節由 Component 宣告＋Config 推導，見 [Descriptor](04_component_descriptor.md) |
| 部署設定（Deployment Settings） | 特定環境的執行與連線綁定，包含服務 URL、認證／Secret 引用、DB／實體索引目標及 Runtime／K8s 資源 |
| Builder DEV | Retrieval Builder 提供的開發／測試環境，涵蓋前後端、測試 Runtime 與可選平台測試資源；既有文件未特別註明的 DEV 指此情境 |
| FTEST／ENT | 使用單位匯出設定後自行部署 Runtime／必要服務的目標環境；不預設平台測試資源或資料會一併移轉 |
| Developer 本機開發環境 | Developer 自行開發與驗證 Component／Service 的環境，與 Builder DEV 分開稱呼 |
| UI Draft（UI 草稿） | 編輯過程中的設定狀態，可保存尚未啟用的方法／欄位；不表示所有內容都參與執行 |
| Effective Config（有效 Config） | 從草稿或輸入設定中，取出實際使用的方法、參數及引用後形成的有效邏輯設定；手動、AI 與手寫設定使用相同驗證規則 |

同一 System、同一 Config Revision 在 Builder DEV／FTEST／ENT 沿用相同邏輯 Config，各環境可使用不同部署設定。例如只換服務 URL 或 Secret 引用屬部署綁定；改 Chunk Size、Query Rewrite Prompt 或模型語意 Profile 屬 Config 變更，不能以環境覆寫掩蓋。System 日後編輯會產生新 Revision，不要求它永遠只有一版 Config。

Builder DEV 與 FTEST／ENT 都使用環境綁定，但用途與管理邊界不同：前者由平台支援開發／測試，後者由使用單位準備部署資源。`DEV test use` 只是選用平台測試資源，不能視為 FTEST／ENT 已有可用連線；匯出時需補齊目標綁定，模型／索引語意仍須相容。Memory 可以沿用到目標環境，不因部署而自動改成 MongoDB；重啟後需重新 Ingestion。責任分工與案例見 [A～E 責任](#src-20-3-最終詳細總表)。

Config 與部署設定的欄位、有效設定規則及範例見 [資料契約：～8](05_system_config.md#src-05-6-config-結構與有效設定)。正式 Schema、檔案包裝與版本綁定仍由 Q-002／Q-015／Q-021 核定；本章的名詞定義不凍結程式型別名稱。

先前助理引入的 **Blueprint 不作正式領域物件**，統一使用 Config／部署設定。Prototype 舊有 RAGBlueprint、blueprint.json、Groups 等標籤／變數的遷移見 資料契約手冊／UI手冊；舊程式名稱不另創正式概念。

<a id="version-terms"></a>

<a id="src-03-34-版本概念"></a>
## 版本概念

| 名詞 | 代表什麼 |
|---|---|
| 開發文件版本 | 本 repository 規格內容的修訂，例如文件集 v0.12；不代表 Config 或程式版本，也不代表功能已完成 |
| Config Revision（config_revision） | 同一 System 的邏輯設定版本；改方法、參數、Prompt 等可形成新版本 |
| 文件內容版本（source_revision） | 每份匯入 Retrieval 的來源文件之內容版本；不同文件各自追蹤 |
| 索引資料版本（index_generation） | 某次可追蹤的索引資料狀態／發布批次，對應納入的文件版本及處理／建索引結果；可涵蓋多份文件 |
| 契約版本（contract_version） | 資料／Config 結構契約的格式版本；目前欄位與遷移規則屬建議，仍待 Q-002 核定 |

本節的「文件內容版本」指**匯入 Retrieval 的來源資料**，與 03～08 Markdown 規格的文件版本不同。改來源內容可在相同 Config 下形成新索引資料；來源不變而改切分／Embedding 也可能需要重建。只改 Inference Prompt 則可沿用相容的索引資料。

各版本不是一對一。相同 Config 的不同環境也可使用不同資料／索引。具體欄位、變更範例及索引相容規則見 [資料契約](05_system_config.md#src-05-2-識別版本與作用域)／[架構與責任相關章節](#src-03-31-系統組成與管理階層)；版本 ID 生成、快照保存及發布原子性仍由 Q-007／Q-010／Q-015 核定。

<a id="src-03-35-元件關係與實作責任"></a>
## 元件關係與實作責任

**04＋05 應足以讓開發者手寫 Config 直接執行 Engine，建立 Retrieval System；不要求 API 才能成立。**06 產生設定，07 保存設定並管理 Runtime 請求。UI 產生 Config，由同一套 Engine 的共用 Flow／Executor 依已驗證快照執行；System 代表設定及資料作用範圍，不要求各自持有一份專屬 Flow 物件。

| 元件 | 責任 | 邊界 |
|---|---|---|
| Builder Frontend | 草稿、表單、預覽、結果與互動 | 後端重新驗證所有請求 |
| Builder Backend | 身分／權限、System／Revision、Dataset、任務、Export、AI 助手服務 | 不重寫模組演算法 |
| Engine | Config 編譯、Registry、初始化、Pipeline、模組及搜尋 Adapter | 不讀取前端草稿或依賴 Builder DB |
| Runtime API | HTTP 對應、任務包裝、Engine 生命週期、健康檢查 | 獨立部署後不依賴 Builder |
| 外部依賴 | LLM、Embedding、Rerank、ES、選配 MongoDB、Secret 與觀測服務 | 不隨 YAML 自動建立 |

技術方向以 Python、Pydantic 與部門既有 LangChain／LangGraph 生態為基礎；使用者已說明部門技術棧，Haystack 是早期比較候選，不是本專案已選框架。固定模組骨架可直接組裝，受控融合路徑不等於通用 DAG 編輯器。套件版本及前後端框架仍見 [Q-001](08_plan_and_decisions.md#q-001)。

<a id="developer-terms"></a>

<a id="src-20-3-最終詳細總表"></a>
## A～E 契約與角色責任總表

| 契約群組 | 包含的子項目與內容 | Admin／平台開發者制定 | Developer 閱讀／遵守 | Developer 交付 | Builder User 操作 | Library 使用 | Builder 使用 | Deploy 使用 | 關係與邊界 |
|---|---|---|---|---|---|---|---|---|---|
| **A. Engine 執行契約** | **資料**：IngestionDocument、ParsedDocument、Chunk、QueryContext、ResultSet 等。<br><br>**執行**：Module／連續區段 I/O、Local 執行介面、Context。<br><br>**索引**：IndexBinding、Artifact Definition。 | 共用資料 Schema、I/O 語意、SDK 執行介面、Context 取得規則；Artifact Definition 格式及相容性規則。 | 自己涵蓋區段的 I/O 與語意。<br><br>**Local**：另看 SDK 介面／必要的 Context 用法。<br><br>**涉及索引**：另看 Binding 與支援的格式。 | 符合契約的實作、輸入輸出範例、契約測試。<br><br>**引入新／未註冊索引格式時**：提供 Artifact Definition（target Schema、讀寫語意、能力限制）及相容 Retrieval／Adapter；沿用已註冊格式則宣告支援。 | — | 執行並傳遞資料、提供 Context、驗證 I/O 與索引相容性。 | 使用測試 API 對外的輸入／輸出格式；不承擔所有內部 SDK 介面。 | — | **B／C 引用 A。**跨 Module 的 Component 遵守核定區段邊界，不強迫回傳所有中間物件。<br><br>IndexBinding 是執行資料；Artifact Definition 是可共用的索引格式規格，屬 A 的擴充規格，不必每個 Component 各寫一份。 |
| **B. Component 定義** | **Descriptor**：識別、版本、涵蓋範圍、共用 I/O 引用、能力／資源。<br><br>**Config Schema**：參數與限制。<br><br>**I/O Data Schema／規則**：固定資料細節、依 Config 細化、上游選項來源與相依條件；六類能力見 [Descriptor](04_component_descriptor.md)。<br><br>UI 提示／呈現語法仍待定。 | Descriptor Schema、Schema 採用規範／必要 Meta-schema、有限細化規則與相依語意；定義不改變 A 的邊界。 | 設定／I/O 宣告、規則支援範圍、能力與資源要求。 | **Local**：Component、Config Schema、I/O 細節／規則及測試，可由 SDK 產出。<br><br>**Remote**：以 C 為來源推導／適配等價描述，避免手寫兩份。 | — | 驗證參數，依 Config／上游規格推導 I/O 與候選，檢查接線；經 Registry 取得實作或 Adapter。 | 產生表單、顯示當前資料規格／選項與相依原因；正式解析器／Registry 尚未實作。 | — | **B 宣告規格，D 提供設定值，A 限制共用格式。**<br><br>細化支援方向已確認，具體 Descriptor／規則鍵名與解析 API 未凍結。任意程式或即時資料決定的規格不屬首版純宣告。 |
| **C. Remote Service 定義** | **Manifest**：服務識別、operations、參數、呼叫資訊、部署／連線需求。<br><br>**Image 分支**：image、啟動／部署描述。<br><br>**External 分支**：既有服務連線及認證綁定需求。 | Manifest Schema、operation 規則、Remote HTTP 請求／回應／參數協定、Image／External 必要資訊；具體格式待定。 | **Remote Developer 才需閱讀**：Manifest、呼叫協定與 operation 的 A 邊界契約；依部署模式看對應交付規格。 | Manifest、可呼叫的服務、API 範例與契約測試。<br><br>**Image**：另附 image 與啟動／部署資訊。<br><br>**External**：由 Developer 部署，交接可用服務及環境連線資訊；環境實際值歸 E。 | — | Adapter 依 operation 呼叫服務，驗證並轉交符合 A 的業務資料。 | 登錄服務、推導 B 的選項；管理 Builder DEV 測試所需的服務啟動或連線。 | **Image**：產生／使用服務部署設定。<br><br>**External**：只綁定既有服務，不部署該服務。 | **operation 導出 B，I/O 遵守 A，環境需求由 E 滿足。**兩種 Remote 模式都可有多個 operation；一個 operation 可涵蓋連續多 Module。<br><br>僅宣告平台需提供／部署／驗證的依賴；Developer 內部自行管理的服務不必全部公開。 |
| **D. System 組裝設定** | **System Config**：Component 選用／版本、參數值、流程、結果處理與邏輯資源引用。<br><br>資料欄位相關設定由所選 Component 開放，不再獨立頂層 document_schema。 | System Config Schema、組裝／相容規則、有效設定的解析與版本包裝。 | 閱讀 Component 選用、參數及資源引用方式。 | 整合範例 Config／測資，展示接上前後段；正式 SDK 前明示草案／離線狀態。 | **主要操作位置**：選 Component、填參數，必要時在 Parser 設定欄位定義／映射。 | 取得 B／C，依參數推導 I/O／相依，驗證後執行。 | 編輯、驗證、測試 Config；顯示推導資料規格與錯誤。 | 將 Config 提供給目標 Runtime。 | **D 保存使用值；資料規格由 B／C＋D 推導。**<br><br>解析規格可作結果／快照，不要求 User 重複手填；不複製完整 Descriptor、Manifest 或 Live Client。 |
| **E. 環境與資源綁定** | Builder DEV／FTEST／ENT 的 Endpoint、Secret 引用、DB／實體索引目標、儲存與部署資源設定。<br><br>涵蓋平台測試資源、自備 DB／模型 API 與 Remote Service 的環境值。 | 環境綁定 Schema、資源類型、Secret 引用、部署／驗證規則；管理平台可提供的資源。 | **需要平台資源或協助部署時**，閱讀綁定與部署規格。 | 必要的綁定範例及部署／連線交接資訊。<br><br>資源「需求」已寫在 B／C，E 示範如何滿足，不重複定義需求。 | 選用資源；自備資源或兼任部署者時補設定。 | 解析綁定、初始化 Client 等資源，透過 A 的 Context 提供。 | 提供 Builder DEV 資源選擇與必要設定介面。 | 注入連線、Secret 引用、儲存及部署資源。 | **E 滿足 B／C 需求，與 D 一起建立可執行 System。**<br><br>同版 D 可搭配不同 E，但需相同邏輯能力。Live Client／索引物件留在 Runtime 程序中，由 Engine 管理生命週期。 |

上表 A～E 的內容可分別存在程式定義、JSON Schema、登錄資料或設定檔；**交付內容不等於要求 Developer 手寫多份 JSON**。SDK 可產出設定 Schema／Descriptor，Remote 可由 Manifest 推導目錄資訊。精確包裝與來源規則待正式介面核定。

<a id="src-03-4-使用流程與執行入口"></a>
## 使用流程與圖面解讀

1. Build：設定 Schema、模組與外部服務，建立 Retrieval System。
2. Ingestion：接收資料，建立 Chunk／Index。
3. Inference：對該 System 測試問題與引用。
4. Evaluation：用 Dataset 檢查品質；不達標回 Edit Config。
5. Export YAML：補齊 FTEST／ENT 服務設定並匯出 Runtime 配置。
6. Deploy YAML in FTEST／ENT：使用單位自行在 K8s 部署。

1～5 與 Edit Config 屬 Builder 測試範圍，6 在其外。這是引導順序；Build 後可匯出草稿，Ingestion／Inference 可重複，Evaluation 不要求先手動檢索查詢。是否強制 Evaluation Release Gate 另決。

流程圖：[L1 PNG](../diagrams/01_user_system_l1.png)、[Mermaid](../diagrams/01_user_system_l1.mmd)、[固定版面 SVG](../diagrams/01_user_system_l1.svg)。架構圖：[PNG](../diagrams/02_infra_architecture.png)、[Mermaid](../diagrams/02_infra_architecture.mmd)。2026-10-27 依使用者要求抽出共用 Retrieval Engine Platform，Runtime 內改標 Retrieval Service，並同步本章名詞／圖面規則。使用者確認後移除 Image→YAML 的「鎖定 Image 版本／Digest」連線並同步更新 PNG；Image 引用仍由 Export 記入 YAML，版本／Digest 規則保留於 07 的部署規格。同日後續 Mermaid 調整為 Platform 邊界直接連到 DEV 與獨立 Runtime，並增加自行部署環境外框；此輪只更新 Mermaid 與本章說明，PNG 保留前次同步版。本次不調整 L1。

圖面的既有使用者要求也屬規格，後續更新須保持：

2026-10-29 新增 Developer 四步 block 及 Module／Component 示意圖：L1 下方依序 D1 下載 repo / 確認開發 contract、D2 開發 Component、D3 測試與 PR 審查、D4 發布並更新 Retrieval Engine Library，再連至共用 Engine 的選用能力。四步是既有開發／交付流程的摘要，精確權限與工具仍待核定，見 [Engine／Component 開發](03_engine_and_components.md#developer-flow-blocks)。Module 圖的 [Mermaid](../diagrams/03_module_component_concept.mmd) 與 [SVG](../diagrams/03_module_component_concept.svg) 維護相同關係；兩圖皆以固定 SVG 版面輸出 PNG。

- L1 的 1～5 左到右同一水平列，與「修改 Config」位於「Retrieval Builder測試」框內；6「Deploy YAML in FTEST/ENT」在框外右側。
- 下方測試實體名稱為「Retrieval System for Retrieval Builder 測試」；6 以虛線連其下方「Retrieval System in k8s」，YAML 設定檔另有虛線連到該實體。
- Evaluation→Export 標示「準備部署到 k8s」；Evaluation→修改 Config 標示「驗證不達標，需調整」。修改後依 Ingestion／Inference 變更返回相應步驟，並以虛線更新測試實體。
- Infra 使用「Retrieval Builder Control Plane」，明列 Frontend／Backend；Config／Validator／服務設定及 Export 合併為 Backend 職責，不因圖面重畫拆成必要微服務。
- tSSO 作登入入口；Backend 的「建立／設定 Runtime」連到整個 DEV Retrieval Runtime 邊界，由 Runtime 內部依 Config 組裝 System 執行實例。
- Retrieval Engine Platform 作為獨立共用實作區塊，展示 Retrieval Engine Library 與共用 Runtime Image；Platform 外框直接以虛線連到 DEV Retrieval Runtime 與獨立 Retrieval Runtime 的外框，表達使用共用執行框架。Runtime Image 保留於 Platform 內，不另由 Image 節點連到 Runtime。DEV／FTEST／ENT 重用相同版本程式／Image，虛線表示程式重用與設定載入，不代表向中央 Platform 發送業務請求。
- Runtime 內保留 Runtime API，原 Retrieval Engine Library 節點改標「Retrieval Service｜System 執行實例」；Engine 名稱保留於共用框架。Config 與各環境部署綁定分開，同一 System／Revision 沿用相同邏輯 Config。Engine 標籤不加「含 Local Search」。
- FTEST/ENT YAML 使用文件形狀；以「自行部署環境｜FTEST / ENT」外框包住 Secret Vault、獨立 Retrieval Runtime、部署依賴及 Logs／Metrics／Traces。Runtime 仍保留內層邊界，Vault／依賴／觀測工具位於 Runtime 外、部署環境內；使用者應用程式與部署操作維持在環境外框外。Config Store 保持簡化；本版圖不畫 Evaluation→Store、Backend→tSSO 線，這是圖面省略，不代表取消評估保存或後端授權驗證。

| 面向 | Builder 測試 | 獨立 Runtime |
|---|---|---|
| 入口 | UI 或已綁定 System 的 API | API；開發時也能直接呼叫 Engine |
| 設定 | Create／Edit／Revision | 載入 Config 與環境覆寫 |
| 外部服務 | DEV test use／使用者提供 | 使用單位提供可達且有權限的服務 |
| 評估 | 平台 Runner、Dataset、報告 | 外部工具可呼叫 Query API，不預設附評估 UI |
| 依賴 | 平台保存管理資料 | 啟動與日常執行不依賴 Builder |

<a id="src-03-44-圖面與現行執行模式的解讀d-62d-66"></a>
### 圖面與現行執行模式的解讀（D-62～D-66）

圖中的 Library＋Config→System A／B／C 表示不同邏輯檢索系統，並非每份 Config 各有 API service、Pod 或專屬 Flow。Builder 由共用 Flow／Executor 依固定快照選 Component，實例／索引資源按作用範圍管理。Infra 圖的 Config Store→System 虛線表示配置來源；實際由 Builder Backend 經可信管理下發，Library 不直連 Builder DB。tSSO 是既有目標入口示意，登入方式仍依 D-60 延後，不代表已選定實作。Evaluation 保留 M6 規劃，不重新加入 Generation。

本輪保留既有圖檔版面；上述解釋與Runtime／部署手冊／Runtime API手冊 的服務／路由規格共同閱讀。整合設定初版與跨文件校對證據見 [System Config](05_system_config.md)／[Descriptor](history/reviews/2026-11-05_spec_alignment_review.md)。

<a id="component-terminology-migration"></a>

<a id="src-03-38-component-命名統一2026-10-29d-43"></a>
## 歷史名稱與遷移對照

使用者確認將原先表示「Module 下的可替換實作」的 Method 統一稱為 **Component（元件）**。Module Developer 角色名稱保留，工作是依 Module 契約開發 Component；Implementation 可作「具體實作」的敘述，不另增一個架構層級。Node 若用於圖面／配置引用，表示具體位置或實例，不與 component_id 混用。

| 舊稱／草案 | 新稱／草案 | 調整範圍 |
|---|---|---|
| Method／Method package | Component／Component package | 文件中的擴充單位與交付套件 |
| method_id | component_id | Registry、Descriptor、Config 目標識別與錯誤定位；範例 ID 值維持不變 |
| BaseMethod／ChunkingMethod | BaseComponent／ChunkingComponent | SDK 類別示意，尚未存在正式 SDK |
| methods/、rag_methods、rag-methods | components/、rag_components、rag-components | rag_engine 內的建議目錄、import package、distribution 名稱；不新增 repo |
| rag_engine.methods | rag_engine.components | 候選 entry point group；精確載入協定仍待核定 |
| method-ui-0.1-draft、目錄 methods、target.kind=method | component-ui-0.1-draft、目錄 components、target.kind=component | 尚未實作的設定描述協定同步改名 |

這是術語及草案介面的一致性更新，沒有改變模組分工、I/O、相依規則或兩個 repo 的部署流程。`module_type`、`implementation_version`、`config_type`、`node_ref` 仍各有用途；不因改名重產生 Component 識別值或自動升級 System。

Python 的 method／`@classmethod`／abstract method、HTTP method，以及融合 Config 中表示演算法的 `method` 保留原義。Prototype 仍使用部分 `method` 選擇欄位，屬明確標示的待遷移草案；不是新 Component Registry 的 component_id。正式 Config 遷移由 Q-002／Q-015 處理，需按格式版本明確映射與檢查衝突，不能全域替換所有 method 或宣稱 Runtime 已接受舊別名。

Engine手冊／Engine／Descriptor 手冊 檔名同步使用 components／component，所有文件內引用更新；歷史敘述中的擴充單位採現行術語，原決策日期與功能狀態保留。L1 的 MMD／SVG／PNG 同步改標籤並保持既有版面與連線；Prototype 的實際介面及內部欄位留待 UIB-010 遷移。

## 主責與一致性規則

共用資料形狀由 schemas/ 與資料契約手冊維護；Module 演算法／SDK 由 Engine 手冊維護；B 的宣告與 DS 候選只在 Descriptor 手冊；D 的 SC 候選只在 System Config；HTTP 與環境限制只在 Runtime 手冊。UI 手冊保存互動與 Prototype 差異，計畫手冊保存已確認基線、Q 與里程碑。

相同議題只有一個主責位置；其他手冊用連結。已確認、候選、已實作／僅模擬、歷史證據必須分開。文件整合不核定任何尚未決定的 DS／SC／Q，也不改變共用資料或產品功能。
