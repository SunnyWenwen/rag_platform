# RAG Builder

Config-driven RAG System 建立與測試平台。

本專案規劃透過 UI 設定模組化 RAG、執行 Ingestion / Inference 測試、QA Evaluation，以及匯出 Kubernetes 部署設定。

目前為架構提案與模擬原型，尚未實作可部署的 RAG Engine。

**後續工作方式（2026-10-16）**：需求先更新文件，對應 Prototype 變更統一記入 [10 UI Backlog](docs/10_ui_adjustment_backlog.md#ui-backlog-pending)，待明確要求改 UI 再實作。本次新增 Fixed-size Chunking 與階段重排只更新文件，原型仍 v0.9。

**名詞定義**：以 [03 §3「名詞定義與元件責任」](03_architecture_proposal.md#terminology) 為唯一依據，包含 Builder／Engine／Runtime／System、Workspace、Module／Method／Pipeline、Config／部署設定及版本概念。

**接續規劃**：先讀 [03 名詞與架構](03_architecture_proposal.md#terminology) 及 [08 開發計畫與決策](docs/08_implementation_plan.md)。原 RAG Builder 規劃對話與「畫userflow」的整合核對、直接修正及需討論的邊界集中於 08 §12；臨時交接摘要已依指示讀取後移除。

## 開發規格文件集 v0.19（2026-10-16）

本輪已把 03～08 整理為 coding agent 可分階段使用的開發規格草案。**已確認方向、既有基線、建議與待決事項分開記錄**；具體公共介面與部分行為仍需決策，不表示後端已實作。v0.10 比對可取得的歷史片段；v0.11 統一 Engine／Runtime／System、Config／部署設定及 Workspace → System，移除正式 Blueprint／Group 概念；v0.12 將正式名詞集中到 03，其他規格引用並補充各自的實作細節。

v0.13 跨對話比對：補齊 I/O 原始問題傳遞、Parser 多路、服務選項、相依卡控與 UI 入口；保留「畫userflow」最新名詞決策。Local Memory／MongoDB 的 Config／部署歸屬、Fusion 計畫及重建期間查詢政策保留待討論，見 08 §12。Prototype 及圖面未改。

v0.14 已確認持久化模式跨環境固定：DEV Memory 則 FTEST／ENT 也用 Memory。Fusion 的位置由 Config 選擇；先討論 [Inference 傳遞物件／多路分數草案](docs/05_data_contracts_search_design.md#inference-state-draft)，再核定處理規則。05 §8.1 區分新增、文件更新、配置重建與重啟恢復；發布／查詢政策仍待討論，最新狀態見 08 §13。

v0.15 曾加入 QueryContext／ResultSet／ResultItem 的具體草案。v0.16 記錄三種 ResultSet 操作與共同排序規則，並同步 [JSON Schema](schemas/inference_context.schema.json)、五份 JSON／[Python 範例](examples/inference/python_example.py)。Contract 形狀為 `inference-0.2-draft`，尚未凍結；[09 UI 整合提案](docs/09_inference_contract_ui_plan.md) 提供順序卡片、ES 輸出粒度、卡控與討論案例，沒有修改 Prototype／Engine。

v0.17 新增 Fixed-size（固定 Token 視窗），保留 Recursive／Header-aware；方法規則與驗收見 04。開發階段重排為 **M0 規格 → M1 最小 Engine → M2 方法／能力擴充 → M3 Runtime API → M4 獨立 AI 設定助手 → M5 Builder 前後端與助手整合 → M6 Evaluation → M7 獨立部署交付**。M4 不需 Builder 即可產生 Config；M5 另驗收 UI 草稿／Diff／套用／取消及過期建議，詳見 08 §4.2。

v0.18 確認 Indexing 預設保存全部 Chunk.fields／metadata，拿掉使用者內容保存投影，Chunking 預設繼承全部有效 metadata；只選全文／向量索引與可過濾欄位。目標 Config 範例省略 stored_fields／metadata_fields，UI 尚未改。Rewrite／Multi-query 的單模組測試與 LLM 結構化輸出策略先記為提案，待確認；詳見 04 §5.1.1、06 §3.3.1 及 10 的 UIB-005～007。

v0.19 討論提案：將 Rewrite／Multi-query 合併為單一 Query Rewrite，以產生數量 1／N 動態建立輸出 Schema；Generation 保留預設格式，在收合進階區明確啟用自訂回答 JSON Schema。自訂內容與平台 API 回應／可信引用分開，主要回答文字路徑與相容政策仍待核定，見 04 §5.1.2／§5.4.1。UIB-008／009 是未完成提案，不表示已確認或改過原型。

| 文件 | 定位 |
|---|---|
| [03 系統概覽與架構](03_architecture_proposal.md) | 正式名詞定義、產品目的、新手／進階情境、元件分工、部署邊界與範圍 |
| [04 Engine 組裝、執行與模組規格](docs/04_module_methods_io_contracts.md) | 手寫 Config 可獨立使用的 Engine、Pipeline、各模組與 Adapter |
| [05 共用資料模型與 Config](docs/05_data_contracts_search_design.md) | ParsedDocument／Chunk／SearchHit、Schema、Config 草案與變更影響 |
| [06 使用流程與 UI 開發規格](docs/06_ui_development_spec.md) | 基本／進階、CSV、AI 助手、預覽、Edit 與測試操作 |
| [07 Backend、Runtime API 與整合](docs/07_backend_runtime_integration.md) | API、System／Revision、任務、持久化、Runtime 與 Export |
| [08 開發計畫、驗收與決策追蹤](docs/08_implementation_plan.md) | M0～M7、助手獨立／UI 兩階段驗收、39 項決策、27 項待決問題及 40 項歷史要求對照 |
| [09 Inference Contract 與 UI 整合提案](docs/09_inference_contract_ui_plan.md) | 三種操作／共同排序的討論記錄、順序式 UI 設定、案例與待確認選項 |
| [10 UI Prototype Backlog 與完成紀錄](docs/10_ui_adjustment_backlog.md) | §1～6 保留 v0.9 歷史完成項目；§7 記錄 Fixed-size／助手整合／內容保存／metadata 待辦與 Rewrite 試跑提案，收到改 UI 指示後才實作 |

建議先讀 03／08，再依任務讀 05／04／07／06。03 統一名詞與邊界，05 定義資料／版本規則，08 記錄決策與待決狀態。Engine 核心不依賴 Builder UI、HTTP 或 Builder DB；07 將其包裝為可管理服務。每份規格末尾列出相關 Q-ID，完整候選／決策／階段阻擋統一放在 08。

舊 04／05 的重複及覆蓋式章節已重整，歷史可由 Git commit `cf4dfdc0e29acc91a2fe63b1993f867c8facaf6d` 查閱。完整 Config 的拼字、型別及預設值仍屬 Q-002 草案；本輪沒有新增 Engine、API 或正式部署功能。

## 原型與圖面

- [UI Prototype](01_ui_prototype.html)：下載後以瀏覽器開啟，模型／搜尋／評估與 API 為模擬。
- [L1 使用流程圖](diagrams/01_user_system_l1.png) · [Mermaid 關係定義](diagrams/01_user_system_l1.mmd) · [固定版面 SVG](diagrams/01_user_system_l1.svg)
- [Infra 架構圖](diagrams/02_infra_architecture.png) · [Mermaid 原始檔](diagrams/02_infra_architecture.mmd)

L1 圖面於 2026-10-28 調整為三層：上方「RAG Builder 測試（for RAG Builder User）」、中間「RAG Engine」、下方「RAG Engine 開發（for RAG Engine Developer）」。角色標示於區塊標題。步驟 1～5 保留由左到右的操作順序；Build 先產出 Config，再與共用 Engine 結合建立測試用 RAG System。Export 產出包含 Config 與部署設定的 YAML，於框外右側的步驟 6 部署，並結合相同 Engine 的 Runtime Image 建立 RAG System in k8s；步驟 6 仍以垂直虛線指向下方的 k8s System。開發區塊中的 Method 發布／更新至 Engine，Engine「提供可選 Module／Method」直接指向步驟 1 Build（設定 Config）。圖面表示角色與建立關係；實際 SDK、發布權限、套件版本與隔離配套仍待討論，不表示已實作或自動升級既有 System。PNG 由同名 SVG 的固定版面產生；Mermaid 維護相同的節點與連線關係，自動排版不作為 PNG 版面。

架構提案與 Infra 圖已整合 2026-10-14 的最新討論：RAG Builder Control Plane 明確分為 Frontend／Backend，接入 tSSO；DEV RAG Runtime 負責測試執行。Backend 的建立／設定連線指向整個 DEV RAG Runtime，由 Runtime 依 Config 組裝 Pipeline 執行實例，並匯出 FTEST／ENT YAML（文件形狀節點），使用單位自行於 K8s 進行 CD 部署；Secret Vault、部署依賴與觀測工具位於獨立 Runtime 框外。UI 可匯出示意 YAML，不代表可直接部署；Engine、Runtime API 及完整部署 Bundle 尚未實作。

## UI Prototype v0.9（2026-10-15）

本次依已確認需求調整既有介面；進階結果處理預設收合，不新增主頁或 DAG 畫布。**新增示範入口**：Create／Edit 頂部「套用設定示範」可選「多 Query · ES Hybrid」「多路 · 評分後合併」「文件去重」，直接觀察卡控與有效流程摘要。

- Create／Edit 最前段增加 Document Schema；預設只提供必填 fields.text。可新增 fields／metadata，設定 string／number／boolean／array、必填、JSON 預設值及 input／parser 來源；未宣告欄位預設拒絕。
- Ingest 本版先支援 ≤1 MB CSV／JSON。CSV 每列是一筆文件，映射目標包含 document_id／source_revision／fields.*／metadata.*；預覽 API payload 與 ParsedDocument，型別／必填／重複 ID 錯誤會阻止模擬匯入。成功後保存 CSV 映射；JSON 直接使用標準 records 契約。
- 提供「先設定 Config」與「從 CSV 開始 · AI 設定助手」兩種入口；確認助手的 Schema、映射與 Pipeline 草稿後，CSV 可帶到 Ingest 再執行。
- 原型舊標籤為 Workspace Groups；正式階層已確認為 Workspace → System。保留卡片與 Edit Config 草稿流程，標籤／內部變數在正式化時遷移。
- Parsing 預設只顯示結構化 JSON；PDF／PPTX／圖片／TXT／Markdown 路由、標題結構與相關說明收在預設關閉的「進階選項」，展開後才顯示。
- 目前原型 Chunking 為 Recursive／Header-aware，Size／Overlap 使用 Tokens，支援 Tokenizer、分隔符及標題層級設定。新增 Fixed-size 已寫入目標規格，尚未改 UI，見 10 §7。
- Embedding 僅 DEV test use／Embedding API；依服務來源展開 URL、認證引用、模型、維度與 Tokenizer 等設定。
- ES 提供 DEV／自行連線；Local Search 只有選 MongoDB 時顯示 DB 設定。
- Index collection 自動由 Workspace＋名稱＋System ID 產生，改名不影響既有實體名稱。
- LLM 服務設定集中管理此 RAG System 的服務清單；Query Transformation／Generation 以 llm_ref 下拉引用，部署時相同服務只需填一次。
- Query Transformation 支援 None／Rewrite／Multi-query；Rewrite／Multi-query 各自可編輯 Prompt，提供 query／count 變數驗證與預覽；原始問題可加入搜尋。
- Retrieval 依 Indexing 與所選欄位推導後端／模式。進階結果處理的同 Query 多路／跨 Query 合併預設勾選，時機各自可在 Retrieval 後或 Reranker 後；ES 已內部融合、單 Query／單一路徑時停用不適用選項並保留草稿。
- ES 內部 Hybrid 保留 Sum Score（預設）／RRF，與平台跨清單合併分開。平台合併提供 RRF（原型預設）／Sum Score，後者可設來源權重、Min–max 轉換或明確確認原始分數可比；真實後端版本／授權與模型能力尚未驗證。
- 固定四處輸出上限：搜尋 Top K、Retrieval 後合併 Top N、Reranker 後 Top N、Reranker 後合併 Top N。依動作啟用／停用，不強制遞減。摘要顯示 Query／路徑／ResultSet 數與候選上限，不冒充實際命中量。
- 去重單位只有 chunk_id／document_id。文件模式另選去重時機，先完成同一時點的 Chunk 融合，再選每份文件最高分的代表 Chunk，最後 Top N。單清單仍可文件去重；若後面仍有合併，需把文件去重後移。
- Rerank 提供 None／DEV／Rerank API。基本區預選一個合法 fields.* 內容欄位，評分後 Top N 預設 3；提問來源獨立顯示，跨 Query 已合併時有效值固定原始問題。逐 Query 提問與額外內容欄位置於進階區，API 說明明列完整候選評分要求。
- Generation 從共用 LLM 清單選擇服務，提供兩層模板、插入變數、完整 Prompt 預覽，以及「模板說明與範例／套用範例」。
- Ingestion API records 使用 document_id／source_revision／fields／metadata，並預覽 Parsing 後的 ParsedDocument；fields／metadata 已使用 Schema 的目標名稱，Parsing 不再重複映射；結構資訊由 Parser 產生。
- Indexing 選可過濾的完整欄位路徑；Retrieval 設定 eq／in 的預設詞值，Inference 可輸入本次 filters，全部以 AND 組合。上游欄位失效會阻止儲存；新增過濾索引需 Ingestion，改詞值只需重測。
- Ingestion／Inference 的「查看 API 端點」提供 Base URL、認證、JSON／multipart、cURL、回應及錯誤範例；Ingestion 另有 run_id 進度查詢。端點與搜尋／過濾仍未實作。
- AI 設定助手明示為規則模擬：可讀小型 JSON／CSV／TXT／MD 樣本（含 records[].fields），先呈現設定差異再套用；不呼叫 AI、不自動 Ingestion。
- 檢查訊息統一標示 [模組／設定]，可點擊定位並展開進階設定；刪除正在使用的 LLM 或評分欄位會保留失效引用並阻止儲存，不靜默換值。
- 編輯 Ingestion 配置後標記需重新匯入；僅 Inference 變更不用重建，但清除舊示意評估。
- 匯出先檢查 DEV 資源，分為待設定草稿及已填妥設定；不匯出真實憑證，Local Search 固定單副本。

所有模型／DB 操作仍是 UI 模擬；Check Settings 只檢查格式。重新整理會重設資料。YAML 使用示例 Engine Image，沒有部署服務或搬移索引。

## 操作示例

1. Create → Document Schema：定義 fields／metadata；接著到 Chunking：改 Header-aware，查看 Tokens 與進階分隔符。
2. Embedding／Indexing：切換 DEV 與自行提供，觀察必填連線設定。
3. Generation → 模板說明與範例：查看兩筆 Chunk 如何組成 context，套用範例。
4. AI 設定助手：輸入「改用 Local Search」，查看差異後套用；樣本可用 JSON `[{"content":"原文","abstract":"摘要","title":"標題"}]`。
5. 建立 → Ingest：上傳 CSV，將 content 映射到 fields.text、department 映射到 metadata.department；檢查預覽後模擬匯入 → Edit Config：改 Chunk Size 後會要求重匯；改 Generation Temperature 則不需重匯。
6. Retrieval → 新增過濾條件：選 metadata.department、eq、manufacturing；再到 Inference 的本次查詢過濾輸入 JSON 條件，與預設條件 AND。
7. Export YAML：DEV 設定可下載草稿；補齊自己的服務 URL 後可匯出格式已填妥的示意設定。
8. System 卡片 → Ingest／Inference → 查看 API 端點：查看 Runtime API、請求與回應；尚未完成 Ingestion 也能查看 Inference 說明。
9. Create → 套用「多 Query · ES Hybrid」→ Retrieval：展開進階，同 Query 合併顯示後端已融合，跨 Query 合併可調整時機。
10. 套用「多路 · 評分後合併」→ Rerank：多份清單逐 Query 評分後合併；切 None 仍保留後置合併。Generation 顯示最終一份清單及候選上限。
11. 套用「文件去重」：即使 ES 只輸出單份結果，仍能按 document_id 去重。改 K／N、去重時機或合併方法，查看可定位的驗證訊息。

## 驗證

v0.9 本次通過：56 項既有規則、23 項新增結果處理規則，以及既有 DOM 事件流程與 13 組新增 DOM 操作。新測試包含四處輸出上限、兩個分組維度、合併時機、None 路徑、文件去重設定、有效／草稿分離、欄位失效、Edit／Cancel、AI 套用、匯出一致性與錯誤定位。

```sh
node tests/prototype.test.cjs
node tests/inference-processing.test.cjs
# 下列兩項需環境可解析 jsdom（本輪使用 26.1.0）：
node tests/prototype.dom.test.cjs
node tests/inference-processing.dom.test.cjs
```

本次沒有可用的受支援瀏覽器檢查流程，因此只完成 VM／jsdom 驗證，**未重跑 v0.9 的視覺版面、手機尺寸或真實瀏覽器互動**。沒有連線模型、DB 或 Runtime。以下 Chromium 記錄僅為舊版歷史，不代表本次新增畫面已完成瀏覽器 QA。

### v0.8 及更早的歷史驗證

執行 `node tests/prototype.test.cjs`，使用無依賴 VM／DOM stub 檢查 56 項設定與狀態規則（包含 3 項非同步樣本讀取）。另以 jsdom 驗證實際表單事件、條件欄位、建立／編輯、AI 套用、Prompt、匯出及 API 說明。已通過 Chromium 互動檢查及 1440px／390px 桌面與手機版面檢查；無頁面 JavaScript 錯誤。檢查涵蓋 Create、API／DB 條件欄位、Prompt 範例、AI 套用、Ingestion、Edit 影響與 Export gate。


共用 LLM／Prompt 另經 Chromium 實測：新增、改名、選擇、刪除、API 設定、Prompt 即時驗證與預覽、共用匯出資源及手機寬度。

API 說明另經 Chromium 實測：兩個操作視窗的開啟／返回、尚未 Ingestion 時查看 Inference 說明、JSON／cURL 範例與手機寬度；沒有送出 HTTP 請求。





Filter／fields 另經 Chromium 驗證：完整欄位路徑、eq／in 值輸入與失效卡控、ParsedDocument 範例、查詢附加條件、手機寬度與匯出。全部為本機模擬，不執行真實資料搜尋。





Document Schema／CSV 流程另經 jsdom 與 Chromium 驗證：兩種起始情境、metadata 必填與映射、保存映射、API／ParsedDocument 預覽、無效 JSON 卡控、Schema 編輯影響／取消，以及 1440px／390px 版面。CSV 讀取、映射、Schema 檢查在瀏覽器執行；LLM、OCR、Embedding、搜尋及 Runtime API 仍是模擬，未送出 HTTP。自動 ID 只在本次上傳內固定，更新既有文件需映射穩定 ID；source_revision 自動值目前僅為示意。



融合方式另經 jsdom／Chromium 驗證選單切換、參數卡控與保留、儲存／Edit、Inference-only 影響、選定策略匯出及桌面／手機版面；本版仍未實作真實分數計算或搜尋。


