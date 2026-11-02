"""Platform-owned adapter: local ABC implementation, remote algorithm execution."""
import httpx
from pydantic import TypeAdapter
from contracts import IngestionDocument, ParsedDocument, validate_structured_json_output
from local_component import ModuleResult, ParserComponent, RunContext

OUTPUT = TypeAdapter(list[ParsedDocument])


class RemoteApiParser(ParserComponent):
    component_id = "example.parsing.remote_api"

    def __init__(self, client: httpx.AsyncClient, endpoint: str):
        # Inject from trusted deployment bindings, not from document content.
        # The caller owns and closes the client; auth/timeout are set there.
        self.client = client
        self.endpoint = endpoint

    async def run(self, data: IngestionDocument,
                  context: RunContext) -> ModuleResult[list[ParsedDocument]]:
        response = await self.client.post(
            self.endpoint,
            json=data.to_payload(),
            headers={"X-Request-ID": context.request_id},
        )
        response.raise_for_status()
        documents = OUTPUT.validate_json(response.content)
        # The remote service is not trusted to validate its own output.
        validate_structured_json_output(data, documents)
        return ModuleResult(data=documents)
