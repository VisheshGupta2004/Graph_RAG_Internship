from __future__ import annotations

from typing import Any

from ..core.config import (
    CONCEPT_COLLECTION,
    IMAGE_COLLECTION,
    RELATION_COLLECTION,
    TEXT_COLLECTION,
    WEAVIATE_GRPC_PORT,
    WEAVIATE_HOST,
    WEAVIATE_PORT,
)


def setup_weaviate() -> Any:
    """Connect to local Weaviate and create MVP collections if needed."""
    import weaviate
    import weaviate.classes.config as wvcc
    from weaviate.classes.init import AdditionalConfig, Timeout

    client = weaviate.connect_to_local(
        host=WEAVIATE_HOST,
        port=WEAVIATE_PORT,
        grpc_port=WEAVIATE_GRPC_PORT,
        additional_config=AdditionalConfig(timeout=Timeout(init=30, query=60, insert=120)),
    )

    try:
        _ensure_text_collection(client, wvcc)
        _ensure_image_collection(client, wvcc)
        _ensure_relation_collection(client, wvcc)
        _ensure_concept_collection(client, wvcc)
    except Exception:
        client.close()
        raise
    return client


def reset_text_collection() -> None:
    """Drop and recreate only TextChunk."""
    client = setup_weaviate()
    try:
        if client.collections.exists(TEXT_COLLECTION):
            client.collections.delete(TEXT_COLLECTION)
        import weaviate.classes.config as wvcc

        _ensure_text_collection(client, wvcc)
    finally:
        client.close()


def reset_image_collection() -> None:
    """Drop and recreate only ImageChunk."""
    client = setup_weaviate()
    try:
        if client.collections.exists(IMAGE_COLLECTION):
            client.collections.delete(IMAGE_COLLECTION)
        import weaviate.classes.config as wvcc

        _ensure_image_collection(client, wvcc)
    finally:
        client.close()


def reset_relation_collection() -> None:
    """Drop and recreate only RelationChunk."""
    client = setup_weaviate()
    try:
        if client.collections.exists(RELATION_COLLECTION):
            client.collections.delete(RELATION_COLLECTION)
        import weaviate.classes.config as wvcc

        _ensure_relation_collection(client, wvcc)
    finally:
        client.close()


def reset_concept_collection() -> None:
    """Drop and recreate only ConceptNode."""
    client = setup_weaviate()
    try:
        if client.collections.exists(CONCEPT_COLLECTION):
            client.collections.delete(CONCEPT_COLLECTION)
        import weaviate.classes.config as wvcc

        _ensure_concept_collection(client, wvcc)
    finally:
        client.close()


def _ensure_text_collection(client: Any, wvcc: Any) -> None:
    if client.collections.exists(TEXT_COLLECTION):
        return
    _create_collection(
        client,
        wvcc,
        name=TEXT_COLLECTION,
        properties=[
            wvcc.Property(name="chunk_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="content", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="title", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="parent_title", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="concept_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="section_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="source_file", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="type", data_type=wvcc.DataType.TEXT),
            wvcc.Property(
                name="metadata",
                data_type=wvcc.DataType.OBJECT,
                nested_properties=[
                    wvcc.Property(name="level", data_type=wvcc.DataType.INT),
                    wvcc.Property(name="breadcrumb", data_type=wvcc.DataType.TEXT_ARRAY),
                    wvcc.Property(name="child_titles", data_type=wvcc.DataType.TEXT_ARRAY),
                    wvcc.Property(name="content_length", data_type=wvcc.DataType.INT),
                ],
            ),
        ],
    )


def _ensure_image_collection(client: Any, wvcc: Any) -> None:
    if client.collections.exists(IMAGE_COLLECTION):
        return
    _create_collection(
        client,
        wvcc,
        name=IMAGE_COLLECTION,
        properties=[
            wvcc.Property(name="image_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="description", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="title", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="parent_title", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="concept_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="section_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="source_file", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="type", data_type=wvcc.DataType.TEXT),
            wvcc.Property(
                name="metadata",
                data_type=wvcc.DataType.OBJECT,
                nested_properties=[
                    wvcc.Property(name="linked_text_section_id", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="caption", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="svg_text_labels", data_type=wvcc.DataType.TEXT_ARRAY),
                    wvcc.Property(name="view_box", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="order_in_file", data_type=wvcc.DataType.INT),
                    wvcc.Property(name="raw_svg_excerpt", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="breadcrumb", data_type=wvcc.DataType.TEXT_ARRAY),
                    wvcc.Property(name="placeholder", data_type=wvcc.DataType.BOOL),
                ],
            ),
        ],
    )


def _ensure_relation_collection(client: Any, wvcc: Any) -> None:
    if client.collections.exists(RELATION_COLLECTION):
        return
    _create_collection(
        client,
        wvcc,
        name=RELATION_COLLECTION,
        properties=[
            wvcc.Property(name="relation_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="source_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="target_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="relation_type", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="description", data_type=wvcc.DataType.TEXT),
            wvcc.Property(
                name="metadata",
                data_type=wvcc.DataType.OBJECT,
                nested_properties=[
                    wvcc.Property(name="source_file", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="sheet_name", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="row_number", data_type=wvcc.DataType.INT),
                    wvcc.Property(name="source_label", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="target_label", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="evidence", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="placeholder", data_type=wvcc.DataType.BOOL),
                ],
            ),
        ],
    )


def _ensure_concept_collection(client: Any, wvcc: Any) -> None:
    if client.collections.exists(CONCEPT_COLLECTION):
        return
    _create_collection(
        client,
        wvcc,
        name=CONCEPT_COLLECTION,
        properties=[
            wvcc.Property(name="concept_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="label", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="node_type", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="text_chunk_ids", data_type=wvcc.DataType.TEXT_ARRAY),
            wvcc.Property(name="image_ids", data_type=wvcc.DataType.TEXT_ARRAY),
            wvcc.Property(name="source_relation_ids", data_type=wvcc.DataType.TEXT_ARRAY),
            wvcc.Property(name="target_relation_ids", data_type=wvcc.DataType.TEXT_ARRAY),
            wvcc.Property(
                name="metadata",
                data_type=wvcc.DataType.OBJECT,
                nested_properties=[
                    wvcc.Property(name="source_files", data_type=wvcc.DataType.TEXT_ARRAY),
                    wvcc.Property(name="titles", data_type=wvcc.DataType.TEXT_ARRAY),
                    wvcc.Property(name="relation_types", data_type=wvcc.DataType.TEXT_ARRAY),
                    wvcc.Property(name="text_chunk_count", data_type=wvcc.DataType.INT),
                    wvcc.Property(name="image_count", data_type=wvcc.DataType.INT),
                    wvcc.Property(name="source_relation_count", data_type=wvcc.DataType.INT),
                    wvcc.Property(name="target_relation_count", data_type=wvcc.DataType.INT),
                    wvcc.Property(name="has_evidence", data_type=wvcc.DataType.BOOL),
                    wvcc.Property(name="embedding_source", data_type=wvcc.DataType.TEXT),
                    wvcc.Property(name="retrieval_weight", data_type=wvcc.DataType.NUMBER),
                ],
            ),
        ],
    )


def _create_collection(client: Any, wvcc: Any, name: str, properties: list[Any]) -> None:
    vector_config = wvcc.Configure.Vectors.self_provided()
    try:
        client.collections.create(name=name, vector_config=vector_config, properties=properties)
    except TypeError:
        client.collections.create(name=name, vectorizer_config=vector_config, properties=properties)
