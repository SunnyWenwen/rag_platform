"""Index store selection: Builder test ES ("dev_test") or a PLED cluster ("pled_es")."""

from __future__ import annotations

from typing import Any

from rag_engine.adapters.index_store import IndexStore, InMemoryIndexStore
from rag_engine.core.errors import ConfigInvalid
from rag_engine.runtime.settings import Settings


class StoreProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._memory = InMemoryIndexStore()
        # Keyed by URL and credentials: a rotated password gets a new client. Never log the key.
        self._stores: dict[tuple[str, str | None, str | None], Any] = {}

    @property
    def memory(self) -> InMemoryIndexStore:
        return self._memory

    def default(self) -> IndexStore:
        """The deployment-bound store used for "dev_test" and for probes of unloaded Systems."""
        if self._settings.index_backend == "memory":
            return self._memory
        if not self._settings.es_url:
            raise ConfigInvalid("RAG_ES_URL is not configured for the Builder test ES")
        password = self._settings.es_password.get_secret_value() if self._settings.es_password else None
        return self._elasticsearch(self._settings.es_url, self._settings.es_username, password)

    def pled_configured(self) -> bool:
        """True when Systems on this Runtime may keep their index on a PLED cluster."""
        return self._settings.index_backend == "elasticsearch" and bool(self._settings.pled_es_url_template)

    def for_connection(self, connection: dict[str, Any]) -> IndexStore:
        if self._settings.index_backend == "memory" or connection["service_source"] == "dev_test":
            return self.default()
        template = self._settings.pled_es_url_template
        if not template:
            raise ConfigInvalid(
                "RAG_PLED_ES_URL_TEMPLATE is not configured",
                path="/config/pipelines/ingestion/indexing/parameters/es_number",
            )
        url = template.format(es_number=connection["es_number"])
        return self._elasticsearch(url, connection.get("account"), connection.get("password"))

    def _elasticsearch(self, url: str, username: str | None, password: str | None) -> IndexStore:
        key = (url, username, password)
        store = self._stores.get(key)
        if store is None:
            from elasticsearch import AsyncElasticsearch

            from rag_engine.adapters.es_store import ElasticsearchIndexStore

            options: dict[str, Any] = {"verify_certs": self._settings.es_verify_certs, "request_timeout": 30}
            if username and password:
                options["basic_auth"] = (username, password)
            if self._settings.es_ca_certs:
                options["ca_certs"] = self._settings.es_ca_certs
            client = AsyncElasticsearch(hosts=[url], **options)
            store = ElasticsearchIndexStore(client)
            self._stores[key] = store
        return store

    async def close(self) -> None:
        for store in self._stores.values():
            await store.close()
        self._stores.clear()
