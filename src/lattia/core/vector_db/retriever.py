from typing import Any

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

    def _to_relevant(self, hits: list[qm.ScoredPoint]) -> list[RelevantQuestion]:
        out: list[RelevantQuestion] = []
        for h in hits:
            payload: dict[str, Any] = h.payload or {}
            out.append(
                RelevantQuestion(
                    id=str(h.id),
                    domain_title=str(payload.get("domain_title", "")),
                    key=str(payload.get("key", "")),
                    label=str(payload.get("label", "")),
                    options=dict(payload.get("options", {}) or {}),
                )
            )
        return out

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
        return self._to_relevant(hits)

    def retrieve_many(
        self,
        queries: list[str],
        top_k: int = 5,
        score_threshold: float | None = None,
        qfilter: qm.Filter | None = None,
        batch: int = 128,
    ) -> list[list[RelevantQuestion]]:
        """
        Optimized multi-query retrieval.
        - Embeds queries in batches, single RPC per batch using search_batch.
        - Returns results aligned to the input order, one list per query.
        """
        if not queries:
            return []

        all_results: list[list[RelevantQuestion]] = []
        for i in range(0, len(queries), batch):
            sub_q = queries[i : i + batch]
            vectors = self.provider.embed(sub_q)
            batch_hits = self.store.search_batch(
                name=self.collection,
                query_vectors=vectors,
                top_k=top_k,
                score_threshold=score_threshold,
                query_filter=qfilter,
            )
            for hits in batch_hits:
                all_results.append(self._to_relevant(hits))
        return all_results
