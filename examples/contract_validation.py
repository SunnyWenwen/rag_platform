"""Runtime-format checks shared by the offline contract validators."""

from jsonschema import FormatChecker


def contract_formats(document_schema):
    formats = FormatChecker()
    document_id = document_schema["$defs"]["document_id"]

    @formats.checks(document_id["format"], raises=UnicodeError)
    def utf8_document_id(value):
        return not isinstance(value, str) or len(value.encode("utf-8")) <= document_id["maxLength"]

    return formats
