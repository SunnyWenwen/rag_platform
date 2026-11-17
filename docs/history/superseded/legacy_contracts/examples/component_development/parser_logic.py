"""Example Developer algorithm shared by Local and Remote demonstrations."""
from copy import deepcopy
import re
from contracts import IngestionDocument, ParsedDocument

def parse_structured_json(data: IngestionDocument) -> list[ParsedDocument]:
    """One content string/record -> one document with one or more units.

    Demo page delimiter: a standalone === PAGE N === line, N >= 1.
    Without delimiters, preserve the original one-unit behavior.

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
    # Page recognition belongs to this Parser, not to the Chunker or the
    # common IngestionDocument schema. These markers are a demo convention.
    markers = list(re.finditer(r"^=== PAGE ([1-9][0-9]*) ===[ \t]*(?:\r?\n|$)", unit["text"], re.MULTILINE))
    units = [unit]
    if markers:
        if unit["text"][:markers[0].start()].strip():
            raise ValueError("text before the first page marker has no declared page")
        if "page" in unit:
            raise ValueError("page is derived from markers; do not also supply content.page")
        pages = [int(marker.group(1)) for marker in markers]
        if pages != sorted(set(pages)):
            raise ValueError("page markers must be unique and increasing")
        units = []
        for i, marker in enumerate(markers):
            end = markers[i+1].start() if i+1 < len(markers) else len(unit["text"])
            page_text = unit["text"][marker.end():end].strip()
            if not page_text:
                raise ValueError("this demo Parser rejects blank pages")
            page_unit = deepcopy(unit)
            page_unit.update(text=page_text, page=pages[i])
            units.append(page_unit)
    return [ParsedDocument(document_id=data.document_id, source_revision=data.source_revision,
                           units=units, metadata=deepcopy(data.metadata))]
