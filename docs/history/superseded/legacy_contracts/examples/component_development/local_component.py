"""Local-only SDK sketch; not imported by the remote service."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict
from contracts import (IngestionDocument, ParsedDocument,
                       validate_structured_json_output)
from parser_logic import parse_structured_json

T = TypeVar("T")


@dataclass(frozen=True)
class RunContext:
    request_id: str  # demo subset, not the full production context


@dataclass
class ModuleResult(Generic[T]):
    data: T  # production metrics/errors and lifecycle signatures remain pending


class ParserConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No algorithm parameters for this particular demonstration Parser.


class ParserComponent(ABC):
    component_id: str
    config_type: type[BaseModel] = ParserConfig

    @classmethod
    def config_schema(cls) -> dict:
        return cls.config_type.model_json_schema()

    @abstractmethod
    async def run(self, data: IngestionDocument,
                  context: RunContext) -> ModuleResult[list[ParsedDocument]]:
        ...

    async def aclose(self) -> None:
        pass  # resources managed by a real Component may require cleanup


class StructuredJsonParser(ParserComponent):
    component_id = "example.parsing.structured_json"

    async def run(self, data, context):
        documents = parse_structured_json(data)
        validate_structured_json_output(data, documents)
        return ModuleResult(data=documents)
