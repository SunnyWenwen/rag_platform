# System Config、模板與版本

## 草稿、有效設定與部署

Workspace 管理多個 System。System ID、Config Revision、source_revision、索引版本、Runtime Image 版本各自獨立。Builder 草稿可保存未啟用方法；編譯只使用所選方法與 Remote 涵蓋區段，拒絕範圍重疊。切回內建方法時恢復原草稿設定。

同一 Config Revision 在 DEV／FTEST／ENT 沿用相同邏輯設定。端點、Secret 引用、DB／索引實體目標及 Runtime 限制屬環境綁定。變更方法、模型語意、維度或資料欄位產生新 Revision，依相依範圍判斷重建。每次請求採單一有效設定快照；有 queued／running Ingestion 時可存草稿，等該 System 工作完成再啟用新版。

## 設定位置

| 模組 | 設定與推導 |
|---|---|
| Import | CSV 映射、來源型態、structdata 欄位與批次參數宣告 |
| Parsing | 單選內建方法或 Remote，依選擇推導 Data[] |
| Chunking | 方法、Tokenizer、來源／輸出欄位及保留欄位 |
| Embedding | 欄位映射、Profile、維度、可選文字組合。Remote 執行 Embedding 時，保留的內建 Chunking 自行指定 Tokenizer |
| Indexing | 全文／向量／Filter 欄位、後端及持久化 |
| Inference Input | 查詢執行參數、型別、必填性與預設值。平台初始化 QueryContext[] |
| Query Transformation／Retrieval／Rerank | 內建方法／模型、查詢參數引用、過濾、融合、Top K／N；也可選 Remote 替換 |
| Remote API | 首節點與連續範圍、服務引用、parameters JSON、Ingestion 輸出欄位及向量宣告 |

有效資料欄位由 Import 與後續有效方法推導，外部 Retrieval 沿用這份 System 候選 Schema。正式鍵名、細化規則的序列化及檔案包裝仍依 Q-002；Prototype 匯出是可查驗的設定示意。

## 執行參數

Import／Inference Input 各自宣告名稱、型別、必填與預設值。Import 的值放在整批 Ingestion Request 的 `parameters`，Inference 的值放在該次查詢的 `parameters`。Runtime 先檢查型別、套預設及拒絕缺少的必填值。下游用 `{{params.name}}` 引用。Remote parameters JSON 中完整參數引用保留原值型別，例如 `{"top_k":"{{params.top_k}}"}` 在值為整數 5 時解析為 `{"top_k":5}`。執行參數留在呼叫環境，與 Data、metadata、索引內容分開。

認證欄位可填固定 Secret reference 或 `{{params.remote_secret_ref}}`。動態引用必須宣告為 `secret_ref`，由 Runtime 檢查本 System 可使用該引用，再解析成認證 Header。一般業務參數傳入 Remote 的 parameters，實際認證憑證走 Header。

## Admin 全域模板

Admin 以版本化設定檔維護全域模板。目錄提供模板 ID、版本、名稱及可套用的邏輯設定。模板可示範內建方法或整組 Remote 設定。對外連線及 Secret 由套用的 System 依環境補齊。Builder 提供唯讀目錄與「選用模板」，把所選版本複製至目前草稿。User 檢查、編輯、驗證及儲存後生效；Admin 更新模板時，既有 System 持續使用已套用的設定。

## 變更影響

- Import／Parsing／Chunking、文件 Embedding 或 Indexing 的有效資料語意變更，依實際相依判斷重跑 Ingestion／重建索引。
- Query Transformation、搜尋／融合、Rerank 或執行參數變更以重新驗證與評估為主。
- 外部 Retrieval 使用自身資料，驗證服務契約、回傳候選及後段相依。
- 環境 Endpoint／Secret 更新後重新做連線與相容驗證。修改未啟用的內建草稿不改執行計畫。

範例見 [Remote API fixtures](../examples/user_remote_api/README.md)，舊 D-66／D-67 的候選稿見[歷史索引](history/superseded/2026-11-11_developer_mode.md)。
