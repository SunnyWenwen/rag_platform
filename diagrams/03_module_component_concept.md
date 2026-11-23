# Module、System Config 與 Remote 範圍

[流程圖](03_module_component_concept.png) · [Mermaid](03_module_component_concept.mmd)

上半部列出首版模組與邊界。Ingestion 共用 Document，Inference 模組共用 QueryContext[]。Runtime 透過[查詢成功物件](../docs/06_runtime_api_and_deployment.md#inference-api)交付結果與版本。外部區段的連線使用 [Remote API v1](../docs/03_engine_and_components.md#remote-api)。索引與檢索沿用同一 Elasticsearch 綁定。Rewrite 的單筆或多 Query 共用同一 Component。

下半部示範用同一份 Library 組裝三套 System。A 直接選用內建元件，B 由 Admin 維護的全域模板起始，C 的 Parsing 接入 User 已部署的 Remote API。

Remote API 可替換單節點或連續區段。涵蓋 Embedding 時宣告 vectors。Remote Retrieval 可直接查詢外部資料，候選 Document 遵守 System 有效的欄位規格。完整範圍見 [Engine](../docs/03_engine_and_components.md#remote-api)。
