# 現行共用 Schema

| Schema | 用途 |
|---|---|
| [data_meta](data_meta.schema.json) | structdata 欄位型別、必填性、搜尋旗標與 Indexing 覆寫 |
| [document](document.schema.json) | Document 外層、content、DenseVector 與檢索候選基礎 |
| [ingestion_request](ingestion_request.schema.json) | 非空 documents 和共用 parameters |
| [inference_request](inference_request.schema.json) | query、filters、metadata、parameters |
| [query_context](query_context.schema.json) | 共用 QueryContext[]，ResultItem.data 承載候選 Document |
| [index_binding](index_binding.schema.json) | 平台管理索引的交接 |

System 的有效欄位與執行參數由設定細化。共用 Schema 的通過不代表任一 System 的契約通過。URI 識別由本地 Schema Registry 解析。[Component Descriptor Meta-schema 草案](component_descriptor.draft.schema.json)與 [System Config Schema 草案](system_config.draft.schema.json)另供[離線驗證](../examples/system_config/README.md)。舊 `IngestionDocument`、`ParsedDocument`、`Chunk` 與舊 `InferenceContext` 的 Schema 和測資已收錄在[歷史契約快照](../docs/history/superseded/legacy_contracts/README.md)。
