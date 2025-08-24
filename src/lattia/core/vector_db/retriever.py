from pydantic import BaseModel
from qdrant_client.http import models as qm

from .embeddings import EmbeddingsProvider
from .qdrant_store import QdrantStore


class RelevantQuestion(BaseModel):
    id: str
    domain_title: str
    key: str
    label: str
    options: dict[str, str]


class SemanticRetriever:
    """
    Thin orchestrator that embeds the query and searches Qdrant.
    """

    def __init__(
        self,
        store: QdrantStore,
        provider: EmbeddingsProvider,
        collection: str,
    ):
        self.store = store
        self.provider = provider
        self.collection = collection

    def retrieve(
        self,
        query_text: str,
        top_k: int = 5,
        score_threshold: float | None = None,
        qfilter: qm.Filter | None = None,
    ) -> list[RelevantQuestion]:
        vec = self.provider.embed([query_text])[0]
        hits = self.store.search(
            name=self.collection,
            query_vector=vec,
            top_k=top_k,
            score_threshold=score_threshold,
            query_filter=qfilter,
        )
        results: list[RelevantQuestion] = []
        for h in hits:
            payload = h.payload or {}
            results.append(
                RelevantQuestion(
                    id=str(h.id),
                    domain_title=str(payload.get("domain_title", "")),
                    key=str(payload.get("key", "")),
                    label=str(payload.get("label", "")),
                    options=dict(payload.get("options", {}) or {}),
                )
            )
        return results
