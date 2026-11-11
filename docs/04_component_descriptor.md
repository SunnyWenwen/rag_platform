# 內建方法描述與有效 Schema 推導

平台維護內建方法的描述與實作。描述保存 Module、方法版本、Config Schema、固定 I/O、可衍生欄位、資源需求及 UI 提示。Builder 用它產生表單、列出有效選項及說明欄位失效原因。Engine 用同一規則編譯有效設定。User 的 Remote API 從 System Config 取得範圍及輸出宣告，由平台產生邊界契約。

## Schema 推導

1. 從 Import 設定取得原始 Document Schema。
2. 依有效方法推導該步輸出。內建方法按規則繼承或衍生欄位。Remote Parsing／Chunking 的外部輸出欄位由 User 宣告。涵蓋 Embedding 時一併宣告向量名稱、來源、維度及 Profile。
3. 將有效輸出用於下游的候選欄位、必填性、型別與相依驗證。選到不存在、型別不符或未保證出現的欄位時保留草稿選值並顯示錯誤。
4. 用同一有效 Schema 產生 Remote Request／Response 預覽和 Runtime 驗證。Inference 共用 QueryContext[]，候選 Document 引用 System 可檢索 Schema。

例：Chunking 保留 text 與 title，Embedding 可選兩者作字串來源。若 Chunking 改名為 body，原 text 映射顯示失效。若 Remote 含 Embedding 並宣告 vectors.body，Indexing 選用 vectors.body，內建向量 Retrieval 再取得對應 Profile 的 Query Encoder。

## 內建描述保留的能力

| 能力 | 例子 |
|---|---|
| 固定欄位 | 內建 Parser 輸出 contenttext |
| 上游繼承 | metadata、文件識別及未改寫的資料欄位 |
| 由 Config 宣告欄位 | Chunking 的輸出與複製欄位 |
| 欄位映射 | structdata.text → vectors.text |
| 動態選項 | 由上游的必填字串提供 Embedding 來源 |
| 條件與相依 | 向量維度／Profile 一致、失效來源提示、有效設定排除未選分支 |

平台內部的 Descriptor Meta-schema、規則鍵名、版本包裝與 UI Renderer 仍依 [開發計畫](08_plan_and_decisions.md#q-002)收斂。既有 D-67 細化及 DS-01～DS-13 的候選格式供平台內部設計查考。舊 Developer 交付及 Manifest 推導範例見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。

## Remote 與模板的來源

System Config 保存 User 的區段選擇、參數引用及實際輸出欄位宣告。模板帶入這些設定的可編輯副本。User 或 AI 助手修改後重新推導與驗證。Remote I/O、參數與錯誤語意見 [Engine](03_engine_and_components.md#remote-api)，環境連線及認證見 [Runtime](06_runtime_api_and_deployment.md#remote-service-deployment)。
