from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from lattia.core.parsers.health_questions import ParsedQuestion, parse_health_questions
from lattia.core.utils.formatting import camel_to_human

from .embeddings import EmbeddingsProvider, OpenAIEmbeddings
from .qdrant_store import QdrantStore

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "urn:lattia:health-questions:v1")


def _canonical_for_hash(q: ParsedQuestion) -> dict[str, Any]:
    """
    Stable structure for hashing that includes metadata.
    If any metadata changes, hash changes, so we treat it as a new doc.
    """
    return {
        "domain_key": q.domain_key,
        "domain_title": q.domain_title,
        "key": q.key,
        "label": q.label,
        "options": q.options,  # <- dict of original options
        # include raw metadata
        "metadata": q.metadata,
    }


def stable_id(q: ParsedQuestion, extra_tag: str = "") -> str:
    s = (
        json.dumps(
            _canonical_for_hash(q),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + extra_tag
        + "5"
    )
    return str(uuid.uuid5(NAMESPACE, s))


def build_embed_text(q: ParsedQuestion) -> str:
    """
    Embed domain title + label + humanized key + options values (when available), in French.
    """
    domain_part = f"Question sur {q.domain_title}: {q.label}"
    key_part = f"Nom du champ: {camel_to_human(q.key)}"
    opts_values = list(q.options.values()) if isinstance(q.options, dict) else []
    if opts_values:
        opts_part = f"Les options sont: {', '.join(map(str, opts_values))}"
        return f"{domain_part}. {key_part}. {opts_part}"
    return f"{domain_part}. {key_part}."


def wait_for_qdrant(url: str, timeout_s: int = 60) -> None:
    import httpx

    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            r = httpx.get(url.rstrip("/") + "/readyz", timeout=3.0)
            if r.status_code == 200:
                return
        except Exception as e:
            last_err = e
        time.sleep(1.0)
    raise RuntimeError(f"Qdrant not ready at {url}/readyz. Last error: {last_err}")


def batch(iterable: list[Any], n: int) -> list[list[Any]]:
    return [iterable[i : i + n] for i in range(0, len(iterable), n)]


def ingest(
    data_path: Path,
    collection: str,
    provider: EmbeddingsProvider,
    qdrant_url: str | None = None,
    qdrant_api_key: str | None = None,
    batch_size: int = 64,
) -> None:
    # Optional: wait until Qdrant reports ready
    t0 = time.time()
    wait_for_qdrant(os.getenv("QDRANT_URL", "http://qdrant:6333"))
    store = QdrantStore(url=qdrant_url, api_key=qdrant_api_key)
    store.ensure_collection(collection, provider.dim, recreate_on_mismatch=True)
    parsed = parse_health_questions(data_path)

    # Prepare ids and payloads
    ids: list[str] = []
    embed_texts: list[str] = []
    payloads: list[dict[str, Any]] = []

    for q in parsed:
        pid = stable_id(q, extra_tag=provider.model_name)
        ids.append(pid)
        embed_texts.append(build_embed_text(q))
        payloads.append(
            {
                "hash_id": pid,
                "domain_key": q.domain_key,
                "domain_title": q.domain_title,
                "key": q.key,
                "label": q.label,
                "options": q.options,  # <- store dict of options
                "metadata": q.metadata,
                # you can add a "version" if you want to rotate collections later
            }
        )

    # Delta detection
    existing_ids = store.list_all_ids(collection)
    incoming_ids = set(ids)
    to_insert_ids = incoming_ids - existing_ids
    to_delete_ids = existing_ids - incoming_ids

    print("---------- Summary of ingest ----------")
    print(f"- Total documents in source: {len(parsed)}")
    print(f"- Total documents in Qdrant: {len(existing_ids)}")
    print(f"- Documents to insert: {len(to_insert_ids)}")
    print(f"- Documents to delete: {len(to_delete_ids)}")
    print(f"- Total time for ingest: {time.time() - t0:.3f} sec")
    print("---------------------------------------")

    if to_delete_ids:
        store.delete_ids(collection, to_delete_ids)

    # Build vectors only for the missing ones
    if to_insert_ids:
        id_to_index = {pid: i for i, pid in enumerate(ids)}
        missing_indices = [id_to_index[pid] for pid in ids if pid in to_insert_ids]
        texts_to_embed = [embed_texts[i] for i in missing_indices]
        payloads_to_use = [payloads[i] for i in missing_indices]
        ids_to_use = [ids[i] for i in missing_indices]

        # Batch embeddings
        for t_ids, t_texts, t_payloads in zip(
            batch(ids_to_use, batch_size),
            batch(texts_to_embed, batch_size),
            batch(payloads_to_use, batch_size),
        ):
            vectors = provider.embed(t_texts)
            upserts: list[tuple[str, list[float], dict[str, Any]]] = []
            for _id, _vec, _p in zip(t_ids, vectors, t_payloads):
                upserts.append((_id, _vec, _p))
            store.upsert(collection, upserts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="One-shot ingest job for Qdrant")
    ap.add_argument(
        "--data-path",
        type=Path,
        default=Path(os.getenv("DATA_FILE", "/usr/app/data/health_questions.fr.json")),
    )

    ap.add_argument(
        "--collection",
        type=str,
        default=os.getenv("QDRANT_COLLECTION", "health_questions"),
    )
    ap.add_argument(
        "--batch-size", type=int, default=int(os.getenv("EMBED_BATCH", "64"))
    )
    args = ap.parse_args(argv)

    ingest(
        data_path=args.data_path,
        collection=args.collection,
        provider=OpenAIEmbeddings(),
        batch_size=args.batch_size,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
