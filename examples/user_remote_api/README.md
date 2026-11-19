# User Remote API 範例

[批次 Ingestion](ingestion.request.json) 提交兩份文件，`source_revision` 分別為 `null` 與 `""`，Runtime 在 Parser 前拆成兩個工作。[第一筆 Remote Request](remote_ingestion.request.json) 傳單份 Document 與業務參數。Runtime 依 Remote 節點的 `auth.bearer_token: "{{PARSER_API_TOKEN}}"` 取得 System Secret 並組成認證 Header。[Parsing → Embedding Response](remote_ingestion.response.json) 保留 `source_revision: null` 並帶具名向量，符合[區段輸出契約](remote_ingestion.response.schema.json)。

[Inference Request](inference.request.json) 的動態 any 群組與 [System Config](../system_config/local_memory.builtin.json) 所示的固定價格條件合併，形成 [Remote Retrieval Request](remote_retrieval.request.json)。外部搜尋[回傳候選](remote_retrieval.response.json)，驗證 [QueryContext[]](../../schemas/query_context.schema.json) 與[由 Ingestion 推導的有效候選 Document](effective_document.schema.json)。此例候選必須有 title、text，可附帶 price、tags 及巢狀 metadata。Remote 收到 QueryContext.filters，並自行決定過濾、排序及截斷。

首版模板由 Admin 維護版本化設定檔，套用時複製設定。這組資料是 HTTP 與 Schema 測資。正式 Config 檔案包裝及 Runtime 連線整合另行驗收。

這組 Remote Ingestion 涵蓋 Parsing → Embedding。另一組 [Remote Parsing Config](../system_config/local_memory.remote_parsing.json) 示範完整的 `config.secret` 和 `auth.bearer_token` 設定，並提供[部署對照](../system_config/README.md#system-secret-examples)。兩組的業務 Request Body 都只帶業務參數。

在 repo 根目錄執行 `python3 examples/user_remote_api/validate.py`，使用 Python jsonschema 與 referencing。
