from __future__ import annotations

from typing import Any

from ..extraction.html_parser import clean_text


def build_concept_nodes(
    text_objects: list[dict[str, Any]],
    image_objects: list[dict[str, Any]],
    relation_objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build ConceptNode objects from chunks and relation endpoints."""
    nodes: dict[str, dict[str, Any]] = {}

    for chunk in text_objects:
        concept_id = clean_text(chunk.get("concept_id", ""))
        if not concept_id:
            continue
        node = _ensure_node(nodes, concept_id, chunk.get("title") or concept_id)
        node["text_chunk_ids"].append(chunk["id"])
        node["metadata"]["source_files"].add(chunk.get("source_file", ""))
        node["metadata"]["titles"].add(chunk.get("title", ""))

    for image in image_objects:
        concept_id = clean_text(image.get("concept_id", ""))
        if not concept_id:
            continue
        node = _ensure_node(nodes, concept_id, image.get("title") or concept_id)
        node["image_ids"].append(image["image_id"])
        node["metadata"]["source_files"].add(image.get("source_file", ""))
        node["metadata"]["titles"].add(image.get("title", ""))

    for relation in relation_objects:
        relation_id = relation["relation_id"]
        source_id = clean_text(relation.get("source_id", ""))
        target_id = clean_text(relation.get("target_id", ""))
        source_label = relation.get("metadata", {}).get("source_label") or source_id
        target_label = relation.get("metadata", {}).get("target_label") or target_id

        if source_id:
            node = _ensure_node(nodes, source_id, source_label)
            node["source_relation_ids"].append(relation_id)
            node["metadata"]["relation_types"].add(relation.get("relation_type", ""))
        if target_id:
            node = _ensure_node(nodes, target_id, target_label)
            node["target_relation_ids"].append(relation_id)
            node["metadata"]["relation_types"].add(relation.get("relation_type", ""))

    return [_finalize_node(node) for _, node in sorted(nodes.items())]


def _ensure_node(nodes: dict[str, dict[str, Any]], concept_id: str, label: str) -> dict[str, Any]:
    if concept_id not in nodes:
        nodes[concept_id] = {
            "concept_id": concept_id,
            "label": clean_text(str(label)) or concept_id,
            "node_type": "concept",
            "text_chunk_ids": [],
            "image_ids": [],
            "source_relation_ids": [],
            "target_relation_ids": [],
            "metadata": {
                "source_files": set(),
                "titles": set(),
                "relation_types": set(),
                "text_chunk_count": 0,
                "image_count": 0,
                "source_relation_count": 0,
                "target_relation_count": 0,
                "has_evidence": False,
                "embedding_source": "not_embedded",
                "retrieval_weight": 0.35,
            },
        }
    return nodes[concept_id]


def _finalize_node(node: dict[str, Any]) -> dict[str, Any]:
    node = dict(node)
    node["text_chunk_ids"] = sorted(set(node["text_chunk_ids"]))
    node["image_ids"] = sorted(set(node["image_ids"]))
    node["source_relation_ids"] = sorted(set(node["source_relation_ids"]))
    node["target_relation_ids"] = sorted(set(node["target_relation_ids"]))

    metadata = dict(node["metadata"])
    metadata["source_files"] = sorted(value for value in metadata["source_files"] if value)
    metadata["titles"] = sorted(value for value in metadata["titles"] if value)
    metadata["relation_types"] = sorted(value for value in metadata["relation_types"] if value)
    metadata["text_chunk_count"] = len(node["text_chunk_ids"])
    metadata["image_count"] = len(node["image_ids"])
    metadata["source_relation_count"] = len(node["source_relation_ids"])
    metadata["target_relation_count"] = len(node["target_relation_ids"])
    metadata["has_evidence"] = bool(node["text_chunk_ids"] or node["image_ids"])
    metadata["retrieval_weight"] = 1.0 if metadata["has_evidence"] else 0.35
    node["metadata"] = metadata
    return node
