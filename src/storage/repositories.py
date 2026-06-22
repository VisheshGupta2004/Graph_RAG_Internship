from __future__ import annotations

import uuid
from typing import Any

from ..core.config import CONCEPT_COLLECTION, IMAGE_COLLECTION, RELATION_COLLECTION, TEXT_COLLECTION


def store_chunks_weaviate(chunks: list[dict[str, Any]], client: Any | None = None) -> dict[str, Any]:
    """Batch insert prepared TextChunk objects into Weaviate."""
    owns_client = client is None
    if client is None:
        from .weaviate_setup import setup_weaviate

        client = setup_weaviate()

    try:
        collection = client.collections.get(TEXT_COLLECTION)
        inserted = 0
        with collection.batch.dynamic() as batch:
            for chunk in chunks:
                object_uuid = _uuid_from_chunk_id(chunk["id"])
                properties, vector = _properties_and_vector(_properties_for_weaviate(chunk))
                _add_object(batch, properties, object_uuid, vector)
                inserted += 1

        failed_objects = collection.batch.failed_objects
        return {
            "attempted": inserted,
            "failed": len(failed_objects),
            "failed_objects": failed_objects,
        }
    finally:
        if owns_client:
            client.close()


def _uuid_from_chunk_id(chunk_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"chp-textchunk:{chunk_id}")


def _properties_for_weaviate(chunk: dict[str, Any]) -> dict[str, Any]:
    properties = dict(chunk)
    properties["chunk_id"] = properties.pop("id")
    return properties


def store_images_weaviate(images: list[dict[str, Any]], client: Any | None = None) -> dict[str, Any]:
    """Batch insert prepared ImageChunk objects into Weaviate."""
    owns_client = client is None
    if client is None:
        from .weaviate_setup import setup_weaviate

        client = setup_weaviate()

    try:
        collection = client.collections.get(IMAGE_COLLECTION)
        inserted = 0
        with collection.batch.dynamic() as batch:
            for image in images:
                object_uuid = _uuid_from_image_id(image["image_id"])
                properties, vector = _properties_and_vector(image)
                _add_object(batch, properties, object_uuid, vector)
                inserted += 1

        failed_objects = collection.batch.failed_objects
        return {
            "attempted": inserted,
            "failed": len(failed_objects),
            "failed_objects": failed_objects,
        }
    finally:
        if owns_client:
            client.close()


def _uuid_from_image_id(image_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"chp-imagechunk:{image_id}")


def store_relations_weaviate(relations: list[dict[str, Any]], client: Any | None = None) -> dict[str, Any]:
    """Batch insert prepared RelationChunk objects into Weaviate."""
    owns_client = client is None
    if client is None:
        from .weaviate_setup import setup_weaviate

        client = setup_weaviate()

    try:
        collection = client.collections.get(RELATION_COLLECTION)
        inserted = 0
        with collection.batch.dynamic() as batch:
            for relation in relations:
                object_uuid = _uuid_from_relation_id(relation["relation_id"])
                batch.add_object(properties=relation, uuid=object_uuid)
                inserted += 1

        failed_objects = collection.batch.failed_objects
        return {
            "attempted": inserted,
            "failed": len(failed_objects),
            "failed_objects": failed_objects,
        }
    finally:
        if owns_client:
            client.close()


def _uuid_from_relation_id(relation_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"chp-relationchunk:{relation_id}")


def store_concepts_weaviate(concepts: list[dict[str, Any]], client: Any | None = None) -> dict[str, Any]:
    """Batch insert prepared ConceptNode objects into Weaviate."""
    owns_client = client is None
    if client is None:
        from .weaviate_setup import setup_weaviate

        client = setup_weaviate()

    try:
        collection = client.collections.get(CONCEPT_COLLECTION)
        inserted = 0
        with collection.batch.dynamic() as batch:
            for concept in concepts:
                object_uuid = _uuid_from_concept_id(concept["concept_id"])
                properties, vector = _properties_and_vector(concept)
                _add_object(batch, properties, object_uuid, vector)
                inserted += 1

        failed_objects = collection.batch.failed_objects
        return {
            "attempted": inserted,
            "failed": len(failed_objects),
            "failed_objects": failed_objects,
        }
    finally:
        if owns_client:
            client.close()


def _uuid_from_concept_id(concept_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"chp-conceptnode:{concept_id}")


def _properties_and_vector(obj: dict[str, Any]) -> tuple[dict[str, Any], list[float] | None]:
    properties = dict(obj)
    vector = properties.pop("_vector", None)
    return properties, vector


def _add_object(batch: Any, properties: dict[str, Any], object_uuid: uuid.UUID, vector: list[float] | None = None) -> None:
    if vector is None:
        batch.add_object(properties=properties, uuid=object_uuid)
    else:
        batch.add_object(properties=properties, uuid=object_uuid, vector=vector)
