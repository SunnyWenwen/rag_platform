"""One executable example per public type; all values are illustrative.

Read in document 17 order. No parser, tokenizer, model or search backend runs here.
"""
from models import *

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
# 將上一個 ParsedDocument 逐 Unit、每 10 字元切分，overlap=0。
# 以下直接列出三筆結果；尚未執行 Embedding，主範例省略 _rag。
chunks = [
    Chunk(
        chunk_id="chunk-demo-001",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "清潔前先斷電。",
            "title": "設備保養手冊",
            "page": 1,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
    Chunk(
        chunk_id="chunk-demo-002",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "每月清潔散熱孔並檢查",
            "title": "設備保養手冊",
            "page": 2,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
    Chunk(
        chunk_id="chunk-demo-003",
        document_id="manual-001",
        source_revision="v1",
        fields={
            "text": "風扇運轉。",
            "title": "設備保養手冊",
            "page": 2,
        },
        metadata={"department": "製造部", "filename": "maintenance.txt"},
        vectors={},
    ),
]

# 後面的 ResultItem 等範例，以第一筆 Chunk 示範。
chunk = chunks[0]
# example:Chunk:end

# example:FilterCondition:start
filter_condition = FilterCondition(
    field="metadata.department", operator="eq", value="製造部",
)
# example:FilterCondition:end

# example:ResultItem:start
result_item = ResultItem(chunk=chunk, score=0.95)
# 沒有數值分數的後端也合法：ResultItem(chunk=chunk)。RRF 讀取陣列位置。
# example:ResultItem:end

# example:ResultSet:start
result_set = ResultSet(key="merged", items=[result_item])
# key 是 Config 可引用的搜尋路徑／群組；items 順序就是排名。
# example:ResultSet:end

# example:QueryContext:start
query_context = QueryContext(
    ori_query="清潔前應注意什麼？",
    query="清潔前應注意什麼？",
    filters=[filter_condition],
    result_sets=[result_set],
    metadata={"language": "zh-TW", "session_tag": "demo"},
)
# example:QueryContext:end

# example:QueryContextList:start
query_contexts: list[QueryContext] = [query_context]
# Query Transformation／Retrieval／Rerank 的 Input、Output 都是這個 list。
# HTTP body 也是 array；沒有 InferenceState 或 data 外框。
# example:QueryContextList:end

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
    artifact_type="builtin.elasticsearch/v1",
    target={"collection": "workspace-demo-system-a"},
    fulltext_fields=["fields.text"],
    filter_fields=["metadata.department"],
    vector_bindings={"text": vector_binding},
)
validate_binding_format(index_binding, ["builtin.elasticsearch/v1"])
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
    "FilterCondition": filter_condition,
    "ResultItem": result_item,
    "ResultSet": result_set,
    "QueryContext": query_context,
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



