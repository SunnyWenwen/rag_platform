# Module、System Config 與 Remote 範圍

[流程圖](03_module_component_concept.png) · [Mermaid](03_module_component_concept.mmd)

Ingestion 共用 Data，Inference 共用 QueryContext[]。圖中兩條外部連線示範支援的範圍。外部候選遵守 System 有效的 Ingestion 輸出欄位規格；使用外部資料時可直接查詢。其餘替換範圍見 [Engine](../docs/03_engine_and_components.md#remote-api)。
