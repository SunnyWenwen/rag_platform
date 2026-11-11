# User Remote API 範例

[批次 Ingestion](ingestion.request.json) 提交兩份文件，Runtime 在 Parser 前拆成兩個工作。[其中一筆 Remote Request](remote_ingestion.request.json) 傳單份 Document 與業務參數，Runtime 從該批次的 Secret reference 解析認證 Header。[Parsing → Embedding Response](remote_ingestion.response.json) 帶具名向量，符合[區段輸出契約](remote_ingestion.response.schema.json)。

[Inference Request](inference.request.json) 經平台入口形成 [Remote Retrieval Request](remote_retrieval.request.json)。外部搜尋[回傳候選](remote_retrieval.response.json)，驗證 [QueryContext[]](../../schemas/query_context.schema.json) 與[由 Ingestion 推導的有效候選 Document](effective_document.schema.json)。此例候選必須有 title、text，外部資料未儲存於平台也採同一規則。

首版模板由 Admin 維護版本化設定檔，套用時複製設定。這組資料是 HTTP 與 Schema 測資。正式 Config 檔案包裝及 Runtime 連線整合另行驗收。

在 repo 根目錄執行 `python3 examples/user_remote_api/validate.py`，使用 Python jsonschema 與 referencing。
