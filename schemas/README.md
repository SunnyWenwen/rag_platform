# 現行共用 Schema

| Schema | 用途 |
|---|---|
| [document](document.schema.json) | Document 外層、content、DenseVector 與檢索候選基礎 |
| [ingestion_request](ingestion_request.schema.json) | 非空 documents 和共用 parameters |
| [inference_request](inference_request.schema.json) | query、filters、metadata、parameters |
| [query_context](query_context.schema.json) | 共用 QueryContext[]，ResultItem.data 承載候選 Document |
| [index_binding](index_binding.schema.json) | 平台管理索引的交接 |

System 的有效欄位與執行參數由設定細化。共用 Schema 的通過不代表任一 System 的契約通過。URI 識別由本地 Schema Registry 解析。[Component Descriptor Meta-schema 草案](component_descriptor.draft.schema.json)與 [System Config Schema 草案](system_config.draft.schema.json)另供[離線驗證](../examples/system_config/README.md)。其他 Schema 保留供[舊驗證](../docs/history/superseded/2026-11-11_developer_mode.md)重現。
