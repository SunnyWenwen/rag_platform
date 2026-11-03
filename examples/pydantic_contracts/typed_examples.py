"""One executable example per public type; all values are illustrative.

Read in document 17 order. No parser, tokenizer, model or search backend runs here.
"""
from models import (
    IngestionDocument, ParsedDocument, DenseVector, Chunk, ResultSourceRef,
    ResultItem, RetrievalSource, Operation, ResultSet, QueryContext,
    InferenceState, ChunkSourceRef, ChunkingIdentity, RagMetadata,
    VectorIndexBinding, IndexBinding, ModuleResult,
)

# example:IngestionDocument:start
ingestion_doc = IngestionDocument(
    document_id="manual-001",
    source_revision="v1",
    content={
        "title": "設備保養手冊",
        "text": "=== PAGE 1 ===\n清潔前先斷電。\n=== PAGE 2 ===\n每月清潔散熱孔並檢查風扇運轉。",
    },
    media_type="application/json",
    metadata={"department": "製造部", "filename": "maintenance.txt"},
)
# example:IngestionDocument:end

# example:ParsedDocument:start
# 示意 Parser 識別分頁標記後的輸出；不是直接呼叫 Parser。
parsed_doc = ParsedDocument(
    document_id=ingestion_doc.document_id,
    source_revision=ingestion_doc.source_revision,
    units=[
        {"text": "清潔前先斷電。", "title": "設備保養手冊", "page": 1},
        {"text": "每月清潔散熱孔並檢查風扇運轉。", "title": "設備保養手冊", "page": 2},
    ],
    metadata=ingestion_doc.metadata.copy(),
)
# example:ParsedDocument:end

# example:DenseVector:start
vector = DenseVector(
    values=[0.1, 0.2, 0.3],  # 教學用三維值；正式維度由模型決定。
    embedding_profile_id="embedding-demo-v1",
    source_field="text",  # 來源是 Chunk.fields.text。
)
# example:DenseVector:end

# example:Chunk:start
# 教學用「每 10 個字元」，overlap=0；正式平台仍以 Tokenizer 計量。
# 每個 Unit 獨立切分，title／page 複製到各自的 Chunk。
chunks = []
for unit in parsed_doc.units:
    text = unit["text"]
    for start in range(0, len(text), 10):
        chunks.append(Chunk(
            chunk_id=f"chunk-demo-{len(chunks) + 1:03d}",
            document_id=parsed_doc.document_id,
            source_revision=parsed_doc.source_revision,
            fields={
                "text": text[start:start + 10],
                "title": unit["title"],
                "page": unit["page"],
            },
            metadata=parsed_doc.metadata.copy(),
            vectors={},  # 尚未執行 Embedding。
        ))

# 後面的 ResultItem 等範例，以第一筆 Chunk 示範。
chunk = chunks[0]
# example:Chunk:end

# example:ResultSourceRef:start
result_source_ref = ResultSourceRef(
    result_set_id="rs-retrieval",
    chunk_id=chunk.chunk_id,
)
# example:ResultSourceRef:end

# example:ResultItem:start
result_item = ResultItem(
    chunk=chunk,
    score=0.95,  # 示意 Reranker 分數，並非機率。
    rank=1,
    source_refs=[result_source_ref],
)
# example:ResultItem:end

# example:RetrievalSource:start
retrieval_source = RetrievalSource(
    route_id="es-hybrid",
    index_ref="idx-demo",
    field_paths=["fields.text", "vectors.text"],
)
# example:RetrievalSource:end

# example:Operation:start
operation = Operation(
    method="cross_encoder",
    parameters={"field": "fields.text"},  # 本例 Component 的示意參數。
    model_ref="rerank-demo-v1",
    scoring_query_id="q-original",
)
# example:Operation:end

# example:ResultSet:start
result_set = ResultSet(
    result_set_id="rs-rerank",
    stage="model_score",
    input_result_set_ids=["rs-retrieval"],
    source=None,  # 非首次檢索，來源由上游 ResultSet 引用表示。
    operation=operation,
    score_kind="reranker_score",
    score_order="higher_is_better",
    items=[result_item],
)
# example:ResultSet:end

# example:QueryContext:start
# 同時保留檢索分數與 Rerank 分數，各自放在不同 ResultSet。
retrieval_set = ResultSet(
    result_set_id="rs-retrieval",
    stage="retrieval",
    input_result_set_ids=[],
    source=retrieval_source,
    operation=Operation(
        method="es_sum_score", parameters={},
        model_ref=None, scoring_query_id=None,
    ),
    score_kind="es_sum_score",
    score_order="higher_is_better",
    items=[ResultItem(chunk=chunk, score=0.83, rank=1, source_refs=[])],
)
query_context = QueryContext(
    query_id="q-original",
    query="清潔前應注意什麼？",
    ori_query_id="q-original",
    ori_query="清潔前應注意什麼？",
    source_query_ids=[],
    result_sets=[retrieval_set, result_set],
    active_result_set_ids=["rs-rerank"],
)
# example:QueryContext:end

# example:InferenceState:start
inference_state = InferenceState(
    contract_version="inference-0.2-draft",
    query_contexts=[query_context],
    active_query_ids=["q-original"],
)
# example:InferenceState:end

# example:ChunkSourceRef:start
chunk_source_ref = ChunkSourceRef(
    unit_index=0,
    field="text",
    output_field="text",
    role="split",
    start=0,
    end=len(parsed_doc.units[0]["text"]),
)
# example:ChunkSourceRef:end

# example:ChunkingIdentity:start
chunking_identity = ChunkingIdentity(
    chunking_fingerprint="0" * 64,  # 實際值須依 15 的規則產生。
    chunk_ordinal=0,  # 此切分任務中的第 1 筆，從 0 起算。
    task_id="text",  # 此例設定的切分任務識別。
)
# example:ChunkingIdentity:end

# example:RagMetadata:start
rag_metadata = RagMetadata(
    source_refs=[
        chunk_source_ref,
        ChunkSourceRef(unit_index=0, field="title", output_field="title", role="copy"),
        ChunkSourceRef(unit_index=0, field="page", output_field="page", role="copy"),
    ],
    chunking=chunking_identity,
)
# 追溯型別的獨立進階範例；主流程 Chunk 範例省略 _rag 以利說明。
# example:RagMetadata:end

# example:VectorIndexBinding:start
vector_binding = VectorIndexBinding(
    embedding_profile_id=vector.embedding_profile_id,
    source_field="text",
    dimensions=3,  # 必須和 values 長度及模型輸出一致。
)
# example:VectorIndexBinding:end

# example:IndexBinding:start
index_binding = IndexBinding(
    contract_version="index-binding-0.1-proposal",
    index_ref="idx-demo",
    system_id="system-A",
    backend="elasticsearch",
    collection="workspace-demo-system-a",
    index_generation="g1",
    mapping_version="mapping-v1",
    document_schema_version="unit-schema-v1",
    capabilities=["fulltext", "dense_vector", "filter"],
    fulltext_fields=["fields.text"],
    filter_fields=["metadata.department"],
    vector_bindings={"text": vector_binding},
    searchable=True,
)
# example:IndexBinding:end

# example:ModuleResult:start
# 以 Parser 的本地呼叫為例；同一個 API 請求也可能解析出多份文件。
module_result = ModuleResult[list[ParsedDocument]](data=[parsed_doc])
parser_http_body = [doc.to_payload() for doc in module_result.data]
# Remote Parser HTTP 回傳 parser_http_body；本地 Adapter 再包成 ModuleResult。
# example:ModuleResult:end

TYPE_EXAMPLES = {
    "IngestionDocument": ingestion_doc,
    "ParsedDocument": parsed_doc,
    "DenseVector": vector,
    "Chunk": chunk,
    "ResultSourceRef": result_source_ref,
    "ResultItem": result_item,
    "RetrievalSource": retrieval_source,
    "Operation": operation,
    "ResultSet": result_set,
    "QueryContext": query_context,
    "InferenceState": inference_state,
    "ChunkSourceRef": chunk_source_ref,
    "ChunkingIdentity": chunking_identity,
    "RagMetadata": rag_metadata,
    "VectorIndexBinding": vector_binding,
    "IndexBinding": index_binding,
    "ModuleResult": module_result,
}

if __name__ == "__main__":
    import json
    print(json.dumps({name: value.to_payload() for name, value in TYPE_EXAMPLES.items()},
                     ensure_ascii=False, indent=2))

