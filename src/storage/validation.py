from __future__ import annotations

from typing import Any


def build_validation_report(
    text_objects: list[dict[str, Any]],
    image_objects: list[dict[str, Any]],
    relation_objects: list[dict[str, Any]],
    concept_objects: list[dict[str, Any]] | None = None,
    embedding_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a small validation report for ingestion artifacts."""
    concept_objects = concept_objects or []
    report = {
        "counts": {
            "textchunk_objects": len(text_objects),
            "imagechunk_objects": len(image_objects),
            "relationchunk_objects": len(relation_objects),
            "conceptnode_objects": len(concept_objects),
        },
        "checks": {
            "text_required_fields": _missing_required(text_objects, ["id", "content", "title", "section_id", "source_file", "concept_id"]),
            "image_required_fields": _missing_required(image_objects, ["image_id", "description", "title", "section_id", "source_file", "concept_id"]),
            "relation_required_fields": _missing_required(relation_objects, ["relation_id", "source_id", "target_id", "relation_type", "description"]),
            "concept_required_fields": _missing_required(concept_objects, ["concept_id", "label", "node_type"]),
            "text_unique_ids": _unique(text_objects, "id"),
            "image_unique_ids": _unique(image_objects, "image_id"),
            "relation_unique_ids": _unique(relation_objects, "relation_id"),
            "concept_unique_ids": _unique(concept_objects, "concept_id"),
        },
    }
    if embedding_summary is not None:
        report["embeddings"] = embedding_summary
    report["passed"] = all(
        value is True or value == []
        for value in report["checks"].values()
    )
    return report


def _missing_required(objects: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    missing = []
    for index, obj in enumerate(objects):
        missing_fields = [field for field in fields if not obj.get(field)]
        if missing_fields:
            missing.append({"index": index, "missing": missing_fields})
    return missing


def _unique(objects: list[dict[str, Any]], field: str) -> bool:
    values = [obj.get(field) for obj in objects if obj.get(field)]
    return len(values) == len(set(values))
