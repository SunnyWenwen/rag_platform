"""Optional FastAPI service template; no Component ABC or Engine dependency."""
from fastapi import FastAPI, HTTPException
from contracts import IngestionDocument, ParsedDocument
from parser_logic import parse_structured_json

app = FastAPI(title="Demonstration Parser API")


@app.post("/parse", response_model=list[ParsedDocument])
async def parse(data: IngestionDocument) -> list[ParsedDocument]:
    try:
        # Replace this function with the Developer's private implementation.
        return parse_structured_json(data)
    except ValueError as exc:
        # Demo 400/422 policy only; production error envelope is still pending.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
