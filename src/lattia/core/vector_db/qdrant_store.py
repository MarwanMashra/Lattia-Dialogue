import os
import time
from typing import Any, Iterable, Optional, Set, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from qdrant_client.http.exceptions import UnexpectedResponse


class QdrantStore:
    """
    Control plane over HTTP for stability, data plane over gRPC for speed.
    Minimal env usage: QDRANT_URL, QDRANT_API_KEY.
    """

    def __init__(self, url: str | None = None, api_key: str | None = None):
        url = url or os.getenv("QDRANT_URL", "http://qdrant:6333")
        api_key = api_key or os.getenv("QDRANT_API_KEY")

        # HTTP client for collection metadata and management
        self._http = QdrantClient(
            url=url,
            api_key=api_key,
            prefer_grpc=False,
        )

        # gRPC client for search, upsert, scroll
        self._grpc = QdrantClient(
            url=url,
            api_key=api_key,
            prefer_grpc=True,
        )

    def ensure_collection(
        self,
        name: str,
        vector_size: int,
        distance: qm.Distance = qm.Distance.COSINE,
        recreate_on_mismatch: bool = True,
    ) -> None:
        """
        Ensure 'name' exists with expected vector size and distance.
        If mismatch, drop and recreate when allowed.
        """
        info = self._get_collection_info_http(name)
        if info is None:
            self._create_collection_http(name, vector_size, distance)
            return

        current = self._extract_vector_params(info)
        mismatch = (
            (current is None) or (current[0] != vector_size) or (current[1] != distance)
        )

        if mismatch:
            if recreate_on_mismatch:
                self._delete_collection_http(name)
                self._create_collection_http(name, vector_size, distance)
            else:
                dim = current[0] if current else None
                dist = current[1] if current else None
                raise RuntimeError(
                    f"Collection '{name}' exists with dim={dim}, distance={dist}, "
                    f"expected dim={vector_size}, distance={distance}."
                )

    def _get_collection_info_http(
        self, name: str, retries: int = 3, base_sleep: float = 0.25
    ):
        """
        Returns CollectionInfo via HTTP, or None if not found.
        Retries briefly on 502/503/504 during early startup.
        """
        attempt = 0
        while True:
            try:
                return self._http.get_collection(name)
            except UnexpectedResponse as e:
                status = getattr(e, "status_code", None) or getattr(
                    getattr(e, "response", None), "status_code", None
                )
                if status == 404:
                    return None
                if status in (502, 503, 504) and attempt < retries:
                    attempt += 1
                    time.sleep(base_sleep * attempt)
                    continue
                raise

    def _create_collection_http(
        self, name: str, vector_size: int, distance: qm.Distance
    ) -> None:
        self._http.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=vector_size, distance=distance),
        )

    def _delete_collection_http(self, name: str) -> None:
        self._http.delete_collection(name)

    @staticmethod
    def _extract_vector_params(
        info: qm.CollectionInfo,
    ) -> Optional[Tuple[int, qm.Distance]]:
        """
        Return (size, distance) for a single-vector collection.
        If multiple named vectors are present or structure is unexpected, return None.
        """
        cfg = info.config.params.vectors

        if isinstance(cfg, qm.VectorParams):
            return cfg.size, cfg.distance

        if isinstance(cfg, dict):
            if len(cfg) == 1:
                vp = next(iter(cfg.values()))
                return vp.size, vp.distance
            return None

        return None

    def list_all_ids(self, name: str, batch: int = 1024) -> Set[str]:
        """
        Scroll the collection and return all IDs as strings.
        """
        all_ids: Set[str] = set()
        next_page: qm.ScrollResult | None = None
        offset = None
        while True:
            points, next_page = self._http.scroll(
                collection_name=name,
                limit=batch,
                with_payload=False,
                with_vectors=False,
                offset=offset,
            )
            for p in points:
                all_ids.add(str(p.id))
            if not next_page or not next_page.next_page_offset:
                break
            offset = next_page.next_page_offset

        return all_ids

    def delete_ids(self, name: str, ids: Iterable[str]) -> None:
        ids = list(ids)
        if not ids:
            return
        self._http.delete(
            collection_name=name,
            points_selector=qm.PointIdsList(points=ids),
        )

    def upsert(
        self, name: str, items: list[tuple[str, list[float], dict[str, Any]]]
    ) -> None:
        if not items:
            return
        points = [
            qm.PointStruct(id=pid, vector=vec, payload=payload)
            for pid, vec, payload in items
        ]
        self._http.upsert(collection_name=name, points=points)

    def search(
        self,
        name: str,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float | None = None,
        query_filter: qm.Filter | None = None,
    ) -> list[qm.ScoredPoint]:
        return self._grpc.search(
            collection_name=name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

    def search_batch(
        self,
        name: str,
        query_vectors: list[list[float]],
        top_k: int = 5,
        score_threshold: float | None = None,
        query_filter: qm.Filter | None = None,
    ) -> list[list[qm.ScoredPoint]]:
        """
        Batched nearest neighbor search for many query vectors.
        Returns a list with one list of ScoredPoint per query vector, in order.
        """
        if not query_vectors:
            return []

        requests = [
            qm.SearchRequest(
                vector=vec,
                limit=top_k,
                with_payload=True,
                with_vector=False,
                score_threshold=score_threshold,
                filter=query_filter,
            )
            for vec in query_vectors
        ]
        return self._grpc.search_batch(collection_name=name, requests=requests)
