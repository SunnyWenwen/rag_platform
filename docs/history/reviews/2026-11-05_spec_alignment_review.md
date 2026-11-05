# 24 — 已確認決策與規格交叉校對

> 歷史校對紀錄，供後續查驗。現行規格由 [08](../../08_implementation_plan.md)及 [23](../../23_system_config_schema_draft.md)維護。

來源：[原始檔案](https://github.com/SunnyWenwen/rag_platform/blob/a27e9cdba06c5ada210b00e09de629b53fe7bae1/docs/24_spec_alignment_review.md)；歸檔日期：2026-11-05。

2026-11-05｜比對基準：D-49～D-65、目前對話及分支 docs/rag-system-factory 的既有文件／共用 Schema／範例。目的為先拉齊既有結論，再提出 [23 System Config 初版](../../23_system_config_schema_draft.md)；本報告不核定 SC 選項。

## 1. 已修正的漏更新與歧義

| 編號 | 發現 | 拉齊後的規則／處理 | 主責位置 |
|---|---|---|---|
| A-01 | 05 範圍與 Chunking 段仍寫 ParsedDocument 五鍵；08 D-05 容易被當現行規格 | 現行為 document_id／source_revision／units／metadata 四鍵；Chunk 六鍵不變。D-05 明標由 D-49 細化 | 05 §1／§6.4、08 D-05、14 |
| A-02 | 13 Structured JSON 範例說 content 轉入 fields | Parser 產出 units 每筆 dict 的直接欄位，Chunker 後才是 Chunk.fields；共用 Schema 不改 | 13 §3.1、14／15 |
| A-03 | 05 仍說 ResultSet.method 是操作記錄；04／08 還有 rank 更新說法 | ResultSet 僅 key／items，名次由 items 位置表示；方法／過程在 Config／Logs，無獨立 method／rank | 04 §5、05 §5、08 D-35、17 |
| A-04 | 04 一段仍說 Config 與資源都從 Context 注入；共用執行示意可能被誤讀為所有模組都有 data 外框 | D-62 是獨立 input／本次 config／Context。示意限本地 Ingestion；Inference 直接傳 QueryContext[] | 04 §2.2.1／§3.1、11／16 |
| A-05 | 05 chunk_id 摘要仍把 fingerprint＋位置演算法當必要 | 必要非空 ID 由 Component 產生；參考 Hash／ordinal／_rag 皆非強制，只有提供時驗證 | 05 §2、15 §1／§5～6、D-52 |
| A-06 | 06／15／08 舊段落把已完成的 UI 模擬列為未改／未實作 | v0.12 已有保存／繼承、任務、模板與原文 Chunk 控制／預覽；真實 Engine／Tokenizer／模型／DB 仍未交付 | 06 §3、15 §9.3、08 Q-002／§9、10 |
| A-07 | 04 留下 checkpoint／取消字句；08 Q-027 還建議不先加 Queue | 首期已有有界記憶體 Queue、不續跑、無工作取消 API；只把分散式持久 Queue／HPA 及具體安全中斷保留後議 | 04 §3.2／§7、08 Q-027、21／22 |
| A-08 | 05 把 execution 列在 D 的候選根，容易混入已定屬 E 的 Runtime 控制 | 共同骨架候選集中於 23；結果處理在 inference，Queue／Rate／Deadline／保存設定在 E／22 | 05 §6.2、20／22／23 |
| A-09 | 18 的私有 Remote 資料管理配套仍只提 ID 清單 | 清單是 documents[]／next_cursor，每筆 document_id＋source_revisions[]；需由實際 Chunk／儲存彙整，不從工作紀錄推定 | 18 文件管理、19／21 §9.3、D-65 |
| A-10 | 圖中 A／B／C 實例及 Config Store 虛線可能被讀成每 Config 一個服務、或 Library 直連 Builder DB | 圖表達邏輯 System／配置來源；實際共用 Flow／API、Backend 可信下發；圖說補充解讀，既有版面不重繪 | 03 §4.4、diagrams 圖說、07／21 |
| A-11 | tSSO 圖示與後續「Builder 登入延後」易混淆 | 圖示是既有目標入口，登入方式尚未凍結；Runtime 暫用單一 Basic 與 Builder 登入分開 | 03 §4.4、07／21 §8 |
| A-12 | Ingestion Schema 的 parsing_profile 描述仍寫 RAG System | 僅描述改為 Retrieval System，欄位／required／來源三選一／Schema ID 不變 | schemas/ingestion_document.schema.json |

## 2. 已核對且保留的基準

- IngestionDocument：單筆與 Parser 共用；HTTP 為非空 List，202 後逐文件結果。ParsedDocument 四鍵／平面 Units；Chunk 六鍵、命名向量、_rag 選填。
- QueryContext[]：ori_query／query／filters／result_sets／metadata；ResultSet key／items、ResultItem Chunk／選填 score；RRF 用名次，Sum Score 仍需可比性。
- 每 System 一組邏輯索引；IndexBinding 五鍵；Runtime 資源／就緒與 Binding 分開。Memory／MongoDB 持久化模式跨環境不被偷偷改寫。
- 共用 Flow／逐次 Config 快照；Component 實例與模型／Client／索引資源作用域分開。Ingestion 結束後才允許新 Config 生效。
- Runtime 記憶體 Queue／狀態、不續跑、不加 Query 讀寫鎖；狀態可查不等於資料已回復。retire 同步 200／deleted 或 not_found，忙碌 409。
- 7 支業務＋2 支 Health；單一 Basic 帳號；可信內部 System 路由；D-65 文件摘要。22 的 14 項 Runtime 初始限制已核定，分頁精確參數仍留定稿階段。
- Local、Remote Image、Remote External 三種模式；連續多 Module 依邊界契約接入；無 data_space_id。一般 User 不填 Developer Service URL，既有模型／DB BYO 仍能由 E 提供。
- Retrieval-only，沒有 Generation；Evaluation 是既有 M6 規劃，未由本次重新增加 Module。UI 仍只維護 backlog，未改 Prototype。

## 3. 本次不代替使用者決定的議題

| 類別 | 保持開放的原因／對應 |
|---|---|
| System Config 根欄位、profiles／tasks／segments／processing | 既有語意已定，但具體表示尚未定；本稿提出 SC-01～SC-10 供核定 |
| Descriptor／Service Manifest／動態 UI Meta-schema | 不能把 mock 目錄或新 fixture 當正式 Developer 交付格式；12／18／Q-028 |
| Profile 定義與可重現交付 | ID 引用必須配合實際模型／版本／維度／Encoding／Tokenizer 定義或鎖；不能只丟一個 ID 就宣稱可部署 |
| 部分寫入失敗、Remote unknown 與資料清理 | failed／unknown 的紀錄已定，實體資料清理／舊版是否可恢復尚未定；Q-008～Q-010／Q-017 |
| source_revision 省略生成與衝突 | 文件摘要可顯示目前版本，不等於已定義版本遞增、同版異內容或過期提交政策；Q-007 |
| Sum Score 轉換、Filter 缺值、Tokenizer 精確邊界 | 結構稿不能代替 Adapter／模型語意，仍需可驗算規格與真實測試；Q-003／004／011／013／014 |
| Prototype 遷移與 Rewrite 1／N 統一 UI | UI 控制項與正式設定並非同一份 Schema；UIB-007／008、SC-10，不因本輪寫檔就核定或改 UI |

## 4. 驗證證據與範圍

基準工作目錄中可讀取的 86 個 Git blobs 與指定 commit 完全一致；另三份既有 PNG 未在本地快取，沒有據此重繪或聲稱逐像素檢查。圖面語意依 MMD／SVG 與圖說核對，既有圖檔版面保留。

既有資料／教學檢查：ParsedDocument 6 正例／12 反例，Chunk 10 項及其負例，Pydantic 15 項，Parser Local／Remote 教學 5 項通過。System Config 草案五個正例／19 個反例通過，涵蓋結構、fixture config_schema、覆蓋範圍、欄位／向量、格式配對與 E 引用；不執行任何真實模型／DB／Remote 服務或 Kubernetes。

最終整批檢查：449 個相對連結及目標 anchor、46 段 Markdown JSON、六份共同／結構 Schema 與 11 份 fixture Component Config Schema 通過；三份既有生成資料區段與 Runtime API 盤點／範例保持原樣。未把瀏覽器舊有紀錄當成本輪重跑 UI，也不把共用 Schema 的描述修正宣稱為資料版本升級。

## 5. 下一步

閱讀 23 的共同骨架與五案例，再依 SC-01～SC-10 討論；先確認 D 的最小根結構與引用、profiles／tasks／segments 表示，再收斂 Profile、結果處理、正規化／E 綁定與遷移。這些選擇完成後才把討論稿移入正式 Config 契約與 SDK，不需要重開已確認的共用資料或 Runtime API 方向。
