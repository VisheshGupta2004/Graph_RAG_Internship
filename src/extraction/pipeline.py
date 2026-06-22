from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.config import EXCEL_PATH
from ..embedding.service import embed_concept_objects, embed_image_objects, embed_text_objects
from ..graph.concept_nodes import build_concept_nodes
from ..graph.relations import extract_relation_chunks, prepare_relations_for_storage
from ..storage import store_chunks_weaviate, store_concepts_weaviate, store_images_weaviate, store_relations_weaviate
from ..storage.validation import build_validation_report
from ..storage.weaviate_setup import setup_weaviate
from .html_parser import build_nested_structure, parse_html
from .image_extraction import extract_image_chunks, prepare_images_for_storage
from .text_chunking import extract_semantic_chunks, prepare_chunks_for_storage


def ingest_html_file(file_path: str | Path, store: bool = False) -> dict[str, Any]:
    parsed = parse_html(file_path)
    nested_json = build_nested_structure(parsed)
    chunks = extract_semantic_chunks(nested_json)
    image_chunks = extract_image_chunks(parsed, nested_json)
    storage_objects = prepare_chunks_for_storage(chunks)
    image_storage_objects = prepare_images_for_storage(image_chunks)
    result = {
        "nested_json": nested_json,
        "semantic_chunks": chunks,
        "image_chunks": image_chunks,
        "storage_objects": storage_objects,
        "image_storage_objects": image_storage_objects,
    }
    if store:
        result["weaviate"] = {
            "text": store_chunks_weaviate(storage_objects),
            "images": store_images_weaviate(image_storage_objects),
        }
    return result


def ingest_html_files(file_paths: list[str | Path], store: bool = False, embed: bool = False) -> dict[str, Any]:
    nested = []
    semantic_chunks = []
    image_chunks = []
    storage_objects = []
    image_storage_objects = []

    for file_path in file_paths:
        result = ingest_html_file(file_path, store=False)
        nested.append(result["nested_json"])
        semantic_chunks.extend(result["semantic_chunks"])
        image_chunks.extend(result["image_chunks"])
        storage_objects.extend(result["storage_objects"])
        image_storage_objects.extend(result["image_storage_objects"])

    relation_chunks = extract_relation_chunks(EXCEL_PATH) if EXCEL_PATH.exists() else []
    relation_storage_objects = prepare_relations_for_storage(relation_chunks)
    embedding_summary = None
    if embed:
        text_embedding_summary = embed_text_objects(storage_objects)
        image_embedding_summary = embed_image_objects(image_storage_objects)
        concept_storage_objects = build_concept_nodes(storage_objects, image_storage_objects, relation_storage_objects)
        concept_embedding_summary = embed_concept_objects(
            concept_storage_objects,
            storage_objects,
            image_storage_objects,
            relation_storage_objects,
        )
        embedding_summary = {
            "enabled": True,
            "text": text_embedding_summary,
            "images": image_embedding_summary,
            "concepts": concept_embedding_summary,
        }
    else:
        concept_storage_objects = build_concept_nodes(storage_objects, image_storage_objects, relation_storage_objects)
        embedding_summary = {"enabled": False}
    validation_report = build_validation_report(
        storage_objects,
        image_storage_objects,
        relation_storage_objects,
        concept_storage_objects,
        embedding_summary,
    )

    output = {
        "nested_json": nested,
        "semantic_chunks": semantic_chunks,
        "image_chunks": image_chunks,
        "relation_chunks": relation_chunks,
        "storage_objects": storage_objects,
        "image_storage_objects": image_storage_objects,
        "relation_storage_objects": relation_storage_objects,
        "concept_storage_objects": concept_storage_objects,
        "validation_report": validation_report,
    }
    if store:
        output["weaviate"] = {
            "text": store_chunks_weaviate(storage_objects),
            "images": store_images_weaviate(image_storage_objects),
            "relations": store_relations_weaviate(relation_storage_objects),
            "concepts": store_concepts_weaviate(concept_storage_objects),
        }
    return output


__all__ = [
    "setup_weaviate",
    "parse_html",
    "build_nested_structure",
    "extract_semantic_chunks",
    "prepare_chunks_for_storage",
    "extract_image_chunks",
    "prepare_images_for_storage",
    "extract_relation_chunks",
    "prepare_relations_for_storage",
    "build_concept_nodes",
    "store_chunks_weaviate",
    "store_images_weaviate",
    "store_relations_weaviate",
    "store_concepts_weaviate",
    "ingest_html_file",
    "ingest_html_files",
]
