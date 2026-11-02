"""Example Developer algorithm shared by Local and Remote demonstrations."""
from copy import deepcopy
from contracts import IngestionDocument, ParsedDocument

def parse_structured_json(data: IngestionDocument) -> list[ParsedDocument]:
    """One content string/record -> one document with one unit.

    This Component deliberately does not accept URI, Base64 or pre-parsed
    content.units. Those require separately declared compatible Parsers.
    """
    if data.content is None:
        raise ValueError("this demo Parser supports content only")
    if data.source_revision is None:
        raise ValueError("supply source_revision; automatic revision policy is not defined here")
    unit = {"text": data.content} if isinstance(data.content, str) else deepcopy(data.content)
    if not isinstance(unit.get("text"), str) or not unit["text"].strip():
        raise ValueError("this demo Parser requires a nonblank text field")
    return [ParsedDocument(document_id=data.document_id, source_revision=data.source_revision,
                           units=[unit], metadata=deepcopy(data.metadata))]

