import os
from typing import Any, Iterable, Optional, Set, Tuple

import grpc
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from qdrant_client.http.exceptions import UnexpectedResponse


class QdrantStore:
    def __init__(self, url: str | None = None, api_key: str | None = None):
        """
        Prefer gRPC for speed while keeping REST as a fallback for endpoints
        not yet supported by gRPC underneath the hood.
        """
        url = url or os.getenv("QDRANT_URL", "http://qdrant:6333")
        api_key = api_key or os.getenv("QDRANT_API_KEY")

        self._client = QdrantClient(
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
        Ensure 'name' exists with the expected vector size and distance.
        If an existing collection mismatches, drop and recreate if allowed.
        """
        try:
            info = self._client.get_collection(name)
        except UnexpectedResponse as e:
            # HTTP path: 404 means the collection does not exist, create it
            status = getattr(e, "status_code", None) or getattr(
                getattr(e, "response", None), "status_code", None
            )
            if status == 404:
                self._create_collection(name, vector_size, distance)
                return
            raise  # some other HTTP error
        except grpc.RpcError as e:
            # gRPC path: NOT_FOUND means the collection does not exist, create it
            if e.code() == grpc.StatusCode.NOT_FOUND:
                self._create_collection(name, vector_size, distance)
                return
            raise  # network errors, permission, etc.

        # If we reach here, the collection exists. Check params.
        current = self._extract_vector_params(info)
        mismatch = (
            (current is None) or (current[0] != vector_size) or (current[1] != distance)
        )

        if mismatch:
            if recreate_on_mismatch:
                self._client.delete_collection(name)
                self._create_collection(name, vector_size, distance)
            else:
                dim = current[0] if current else None
                dist = current[1] if current else None
                raise RuntimeError(
                    f"Collection '{name}' exists with dim={dim}, distance={dist}, "
                    f"expected dim={vector_size}, distance={distance}."
                )

    def _create_collection(
        self, name: str, vector_size: int, distance: qm.Distance
    ) -> None:
        self._client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=vector_size, distance=distance),
        )

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
            # Named vectors, support the common case of a single named vector
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
            points, next_page = self._client.scroll(
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
        self._client.delete(
            collection_name=name,
            points_selector=qm.PointIdsList(points=list(ids)),  # correct selector
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
        self._client.upsert(collection_name=name, points=points)

    def search(
        self,
        name: str,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float | None = None,
        query_filter: qm.Filter | None = None,
    ) -> list[qm.ScoredPoint]:
        return self._client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
