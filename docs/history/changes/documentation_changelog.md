# 文件更新流水帳

> 保存原先 README 的逐輪更新說明，供查驗來源；目前規格請從 [專案入口](../../../README.md)閱讀。

來源：[原始檔案](https://github.com/SunnyWenwen/rag_platform/blob/a27e9cdba06c5ada210b00e09de629b53fe7bae1/README.md)；歸檔日期：2026-11-05。

舊輸入格式、完整單層 YAML、可任意排列結果處理卡片及逐次更新流水帳已移除；歷史由 Git 保留。D-53 已確認預設 Embedding Component 的模板組合與 Chunker 額外原文 Chunk 需求，v0.12 已有配置／模擬預覽，真實 Engine 尚未實作，見 15 §9 與 UIB-018／019。LLM 結構化輸出及正式發布政策仍保留為提案，不當成既定功能。

2026-11-02：ParsedDocument／Chunk 已更新至 0.2-draft（units 與 unit_index 來源追溯）；Prototype v0.12 已同步平面 Units，模擬範圍與限制見 UIB-014。舊 provider 0.1 報告不作新版驗收證據。

2026-11-02 D-50：改為 Retrieval-only；不做 Generation。Library＋Config（及必要資源綁定）建立 Retrieval System，Platform 包含 Library／Runtime API／共用 Image。查詢輸出檢索清單；Rewrite／助手仍可使用 LLM。Prototype v0.12 已遷移產品名稱並移除答案功能，見 UIB-015；底層技術識別另案遷移。repo rag_platform、rag_engine、套件與 Schema ID／_rag 保留為既有技術識別，非產品名稱。


Parser 開發示範：[三種交付模式圖](https://github.com/SunnyWenwen/rag_platform/blob/781fd3e31251739290f93b975aff5696090391d0/diagrams/04_component_delivery_modes.md) → [16 兩種開發方式與程式](../../03_engine_and_components.md)。Remote 服務不要求完整 Engine／ABC；正式 HTTP／參數協定仍待核定。

2026-11-02 D-51：Remote Service 改以 Manifest 註冊供 User 選用，可一次涵蓋連續多 Module；Image 由平台部署，External 固定使用服務既有資料空間，第一版不加入 data_space_id。規格見 18；v0.12 已有 UIB-016 的模擬選取／鎖定／匯出，正式服務管理仍待實作。





2026-11-04 D-55：每 System 一組邏輯索引，IndexBinding 五鍵，省略 index_ref／searchable。索引格式定義、target Schema、Developer 配套及狀態責任見 [19](../../02_data_contracts.md)；共用 [Schema](../../../schemas/index_binding.schema.json)、[格式 target 範例](../../../examples/pydantic_contracts/artifact_definitions.json)。UI 待調整記 UIB-021，未改 Prototype。


2026-11-05 D-56～D-58：Ingestion 統一接非空 IngestionDocument[]，整批預檢才 202、逐文件完整覆寫／結果；工作狀態留 Runtime 記憶體，重啟 unknown。文件存在／document_id 清單直接讀取資料儲存，retire 真正刪除 Chunk／向量與搜尋／持久副本。共用 Queue／Inference 流量控制可配置；後續 D-64 已確認 E 的 Runtime 環境設定、Admin／部署管理者及初始預設，集中見 22。21 為 7 支業務＋2 支 Health，完整 OpenAPI／後端執行細節仍待整理。UIB-022／023 記錄待辦，不改 UI／共用機器 Schema。


2026-11-05 D-59：Remote 未知寫入不自動重試；Builder 登入延後。後續 D-60 已確認不加 Query 讀寫鎖及單一 Basic 帳號，現行規則見 21 §8；ES／Local 直接去重分頁取文件 ID。

2026-11-05 D-60：Builder 共用 Runtime 是同一 API service／程序承載多個 System，service 程序重啟與 Pod 重建分開看。平台不加寫入阻擋 Query 的讀寫鎖，接受更新中讀不一致；同文件重複 Ingestion 拒絕保留。Runtime API 暫採一組 Basic 帳密操作全部 API，Builder 登入延後；未改 UI／Runtime／共用 Schema。


2026-11-05 D-61／D-62：Builder 多份 UI Config 共用一組或少數 Ingestion＋Inference API service，並採 B：共用 Flow／Executor，每次請求固定 Config 快照，各 Module 依設定解析 Component 與逐次參數；不要求每份 Config 建立專屬 Flow。Component 實例與模型／Client／索引資源依狀態及隔離需求分開管理。FTEST／ENT 主 Runtime 初期一 Pod＋一組 API service＋一份 Config，使用相同 Executor；Remote Image 服務仍依需要另外部署。模式見 [03](../../01_architecture.md#runtime-deployment-modes)，執行介面草案見 [04](../../03_engine_and_components.md#shared-flow-execution)，API 範圍與剩餘決策見 [21](../../06_runtime_api_and_deployment.md)；未改 UI／圖面／Runtime 程式。


2026-11-05 D-63／D-64：該 System Ingestion 結束後才允許新版 Config 生效；retire 同步回 200，以 deleted／not_found 區分結果，忙碌文件 409。工作失敗留 Runtime 記憶體可查，重啟／到期 unknown；API 成功／錯誤核心欄位已確認。共用 Runtime 透過可信內部 System 路由選配置，S1 代表 system_id。可調參數集中在 [22](../../06_runtime_api_and_deployment.md)，每頁 100／上限 1,000 等文件 ID 分頁細節仍待確認；未改 UI、Runtime 程式或共用資料 Schema。


2026-11-05 D-65：文件清單改回 documents[]＋next_cursor，每筆為 document_id＋source_revisions[]，從實際儲存 Chunk 去重彙整目前版本；正常單版、更新途中／失敗可能多版，不標示為最新成功版本，也不變更 Chunk.source_revision。定義見 [21 §9.3](../../06_runtime_api_and_deployment.md)，分頁參數與 Runtime 控制仍集中在 22；下一輪建議從完整 System Config、Developer 交付與 SDK 介面收斂，詳見 [08 §7](../../08_plan_and_decisions.md)。


2026-11-05 D-66：完成規格交叉校對，修正舊 ParsedDocument 鍵數、Parser 輸出欄位、ResultSet.method／rank、Context／Config、選填 ID 追溯、UI 模擬狀態與 Queue／Remote 管理描述。新增 [23 整合草案](../../05_system_config.md)／[24 校對紀錄](../reviews/2026-11-05_spec_alignment_review.md)及 [System Config 五案例與離線驗證](../../../examples/system_config/README.md)。草案具體格式尚待核定，不是正式 Engine／SDK 或可部署設定；本輪未改 Prototype。
