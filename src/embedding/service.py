from __future__ import annotations

import os
import math
from functools import lru_cache
from time import perf_counter
from typing import Any

from ..core.config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL


DOCUMENT_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def embed_text_objects(
    text_objects: list[dict[str, Any]],
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> dict[str, Any]:
    """Attach self-provided vectors for TextChunk content."""
    return _embed_objects(
        text_objects,
        text_field="content",
        id_field="id",
        model_name=model_name,
        batch_size=batch_size,
    )


def embed_image_objects(
    image_objects: list[dict[str, Any]],
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> dict[str, Any]:
    """Attach self-provided vectors for ImageChunk descriptions."""
    return _embed_objects(
        image_objects,
        text_field="description",
        id_field="image_id",
        model_name=model_name,
        batch_size=batch_size,
    )


def embed_concept_objects(
    concept_objects: list[dict[str, Any]],
    text_objects: list[dict[str, Any]],
    image_objects: list[dict[str, Any]],
    relation_objects: list[dict[str, Any]],
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> dict[str, Any]:
    """Attach evidence-first self-provided vectors for ConceptNode objects."""
    text_by_id = {obj["id"]: obj for obj in text_objects}
    image_by_id = {obj["image_id"]: obj for obj in image_objects}
    relation_by_id = {obj["relation_id"]: obj for obj in relation_objects}
    relation_only_inputs: list[str] = []
    relation_only_indexes: list[int] = []
    embedded_from_evidence = 0
    embedded_from_relations = 0
    skipped = []

    for index, concept in enumerate(concept_objects):
        metadata = concept.setdefault("metadata", {})
        has_evidence = bool(concept.get("text_chunk_ids") or concept.get("image_ids"))
        metadata["has_evidence"] = has_evidence
        metadata["retrieval_weight"] = 1.0 if has_evidence else 0.35

        weighted_vectors = []
        for chunk_id in concept.get("text_chunk_ids", []):
            vector = text_by_id.get(chunk_id, {}).get("_vector")
            if vector:
                weighted_vectors.append((vector, 1.0))
        for image_id in concept.get("image_ids", []):
            vector = image_by_id.get(image_id, {}).get("_vector")
            if vector:
                weighted_vectors.append((vector, 0.8))

        if weighted_vectors:
            concept["_vector"] = _weighted_average_vector(weighted_vectors)
            metadata["embedding_source"] = "linked_text_image_vectors"
            embedded_from_evidence += 1
            continue

        compact_text = _compact_relation_only_node_text(concept, relation_by_id)
        if compact_text:
            relation_only_inputs.append(compact_text)
            relation_only_indexes.append(index)
        else:
            metadata["embedding_source"] = "missing"
            skipped.append(concept.get("concept_id") or index)

    if relation_only_inputs:
        vectors = embed_passages(relation_only_inputs, model_name=model_name, batch_size=batch_size)
        for index, vector in zip(relation_only_indexes, vectors):
            concept_objects[index]["_vector"] = vector
            concept_objects[index]["metadata"]["embedding_source"] = "relation_label_text"
            embedded_from_relations += 1

    return {
        "model": model_name,
        "evidence_text_weight": 1.0,
        "evidence_image_weight": 0.8,
        "relation_only_retrieval_weight": 0.35,
        "embedded_from_evidence": embedded_from_evidence,
        "embedded_from_relations": embedded_from_relations,
        "embedded": embedded_from_evidence + embedded_from_relations,
        "skipped": skipped,
    }


def embed_passages(
    texts: list[str],
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> list[list[float]]:
    """Embed document/passsage text with the E5 passage prefix."""
    model = _load_model(model_name)
    encode_start = perf_counter()
    vectors = model.encode(
        [f"{DOCUMENT_PREFIX}{text}" for text in texts],
        normalize_embeddings=True,
        convert_to_numpy=True,
        batch_size=batch_size,
    )
    print(
        "[embedding timings] "
        f"operation=embed_passages model={model_name} texts={len(texts)} "
        f"encode_seconds={_elapsed_seconds(encode_start)}",
        flush=True,
    )
    return [vector.astype(float).tolist() for vector in vectors]


def embed_query(query: str, model_name: str = EMBEDDING_MODEL) -> list[float]:
    """Embed a user query with the E5 query prefix."""
    model = _load_model(model_name)
    encode_start = perf_counter()
    vector = model.encode(
        [f"{QUERY_PREFIX}{query}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]
    print(
        "[embedding timings] "
        f"operation=embed_query model={model_name} "
        f"encode_seconds={_elapsed_seconds(encode_start)}",
        flush=True,
    )
    return vector.astype(float).tolist()


def warm_embedding_model(model_name: str = EMBEDDING_MODEL) -> None:
    """Load the embedding model once so the first user query does not pay startup cost."""
    warm_start = perf_counter()
    _load_model(model_name)
    print(
        "[embedding timings] "
        f"operation=warm_model model={model_name} "
        f"warm_seconds={_elapsed_seconds(warm_start)}",
        flush=True,
    )


def _embed_objects(
    objects: list[dict[str, Any]],
    text_field: str,
    id_field: str,
    model_name: str,
    batch_size: int,
) -> dict[str, Any]:
    model = _load_model(model_name)
    embedded = 0
    skipped = []

    for start in range(0, len(objects), batch_size):
        batch = objects[start : start + batch_size]
        inputs = []
        input_indexes = []
        for index, obj in enumerate(batch, start=start):
            text = str(obj.get(text_field, "")).strip()
            if not text:
                skipped.append(obj.get(id_field) or index)
                continue
            inputs.append(f"{DOCUMENT_PREFIX}{text}")
            input_indexes.append(index)

        if not inputs:
            continue

        vectors = model.encode(
            inputs,
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=batch_size,
        )
        for object_index, vector in zip(input_indexes, vectors):
            objects[object_index]["_vector"] = vector.astype(float).tolist()
            embedded += 1

    return {
        "model": model_name,
        "document_prefix": DOCUMENT_PREFIX.strip(),
        "query_prefix": QUERY_PREFIX.strip(),
        "embedded": embedded,
        "skipped": skipped,
    }


@lru_cache(maxsize=2)
def _load_model(model_name: str) -> Any:
    load_start = perf_counter()
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_FLAX", "0")
    os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
    os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Embedding support requires sentence-transformers. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc
    try:
        model = SentenceTransformer(model_name)
        print(
            "[embedding timings] "
            f"operation=load_model model={model_name} "
            f"load_seconds={_elapsed_seconds(load_start)} cache=miss",
            flush=True,
        )
        return model
    except Exception as exc:
        try:
            model = SentenceTransformer(model_name, local_files_only=True)
            print(
                "[embedding timings] "
                f"operation=load_model model={model_name} "
                f"load_seconds={_elapsed_seconds(load_start)} cache=miss local_files_only=true",
                flush=True,
            )
            return model
        except Exception as local_exc:
            raise RuntimeError(
                f"Could not load embedding model '{model_name}'. "
                "Download it once with network access, then rerun embedding locally."
            ) from local_exc


def _elapsed_seconds(start: float) -> float:
    return round(perf_counter() - start, 3)


def _weighted_average_vector(weighted_vectors: list[tuple[list[float], float]]) -> list[float]:
    if not weighted_vectors:
        return []
    dimension = len(weighted_vectors[0][0])
    sums = [0.0] * dimension
    total_weight = 0.0
    for vector, weight in weighted_vectors:
        if len(vector) != dimension:
            continue
        total_weight += weight
        for index, value in enumerate(vector):
            sums[index] += float(value) * weight
    if total_weight:
        sums = [value / total_weight for value in sums]
    norm = math.sqrt(sum(value * value for value in sums))
    if norm:
        sums = [value / norm for value in sums]
    return sums


def _compact_relation_only_node_text(concept: dict[str, Any], relation_by_id: dict[str, dict[str, Any]]) -> str:
    relation_ids = list(concept.get("source_relation_ids", [])) + list(concept.get("target_relation_ids", []))
    relation_descriptions = []
    for relation_id in relation_ids[:10]:
        relation = relation_by_id.get(relation_id)
        if relation and relation.get("description"):
            relation_descriptions.append(str(relation["description"]))
    metadata = concept.get("metadata", {})
    relation_types = ", ".join(metadata.get("relation_types", []))
    parts = [
        str(concept.get("label", "")),
        f"Relation types: {relation_types}" if relation_types else "",
        " ".join(relation_descriptions),
    ]
    return " ".join(part for part in parts if part).strip()
