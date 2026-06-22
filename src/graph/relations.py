from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import openpyxl

from ..core.concepts import concept_id
from ..extraction.html_parser import clean_text


def extract_relation_chunks(excel_path: str | Path) -> list[dict[str, Any]]:
    """Build RelationChunk edges from the CHP WRCF workbook."""
    path = Path(excel_path)
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    relations: list[dict[str, Any]] = []
    seen: set[str] = set()

    for sheet in workbook.worksheets:
        rows = list(_rows_as_dicts(sheet))
        for row_number, row in rows:
            for relation in _relations_for_row(path.name, sheet.title, row_number, row):
                key = relation["relation_id"]
                if key not in seen:
                    seen.add(key)
                    relations.append(relation)

    return relations


def prepare_relations_for_storage(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared = []
    seen: set[str] = set()
    for relation in relations:
        relation_id = clean_text(relation.get("relation_id", ""))
        if not relation_id or relation_id in seen:
            continue
        if not all(clean_text(relation.get(field, "")) for field in ("source_id", "target_id", "relation_type", "description")):
            continue
        seen.add(relation_id)
        prepared.append(
            {
                "relation_id": relation_id,
                "source_id": relation["source_id"],
                "target_id": relation["target_id"],
                "relation_type": relation["relation_type"],
                "description": relation["description"],
                "metadata": relation["metadata"],
            }
        )
    return prepared


def _rows_as_dicts(sheet: Any) -> list[tuple[int, dict[str, Any]]]:
    values = [row for row in sheet.iter_rows(values_only=True) if any(cell is not None for cell in row)]
    if not values:
        return []
    headers = [clean_text(str(header)) if header is not None else "" for header in values[0]]
    rows = []
    for row_index, row in enumerate(values[1:], start=2):
        data = {}
        for header, value in zip(headers, row):
            if header:
                data[header] = clean_text(str(value)) if value is not None else ""
        rows.append((row_index, data))
    return rows


def _relations_for_row(source_file: str, sheet_name: str, row_number: int, row: dict[str, Any]) -> list[dict[str, Any]]:
    if sheet_name == "FG & PWO":
        relations = [
            _make_relation(source_file, sheet_name, row_number, row.get("Functional Group (FG)", ""), row.get("Primary Work Object (PWO)", ""), "has_pwo", row)
        ]
        for dependency in _split_dependencies(row.get("Dependency Links", "")):
            relations.append(_make_relation(source_file, sheet_name, row_number, row.get("Primary Work Object (PWO)", ""), dependency, "depends_on", row))
        return relations
    if sheet_name == "SWO":
        return [_make_relation(source_file, sheet_name, row_number, row.get("PWO", ""), row.get("Secondary Work Object (SWO)", ""), "has_swo", row)]
    if sheet_name == "Skills":
        return [_make_relation(source_file, sheet_name, row_number, row.get("SWO", ""), row.get("Skill", ""), "has_skill", row)]
    if sheet_name == "Tasks":
        return [_make_relation(source_file, sheet_name, row_number, row.get("Skill", ""), row.get("Task", ""), "has_task", row)]
    if sheet_name == "Control Point":
        return [_make_relation(source_file, sheet_name, row_number, row.get("Task", ""), row.get("Control Point", ""), "has_control_point", row)]
    return []


def _make_relation(
    source_file: str,
    sheet_name: str,
    row_number: int,
    source_label: str,
    target_label: str,
    relation_type: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    source_label = clean_text(source_label)
    target_label = clean_text(target_label)
    relation_id = _stable_relation_id(source_file, sheet_name, row_number, source_label, target_label, relation_type)
    description = f"{source_label} {relation_type.replace('_', ' ')} {target_label}."
    return {
        "relation_id": relation_id,
        "source_id": concept_id(source_label),
        "target_id": concept_id(target_label),
        "relation_type": relation_type,
        "description": clean_text(description),
        "metadata": {
            "source_file": source_file,
            "sheet_name": sheet_name,
            "row_number": row_number,
            "source_label": source_label,
            "target_label": target_label,
            "evidence": _evidence_text(row),
            "placeholder": False,
        },
    }


def _split_dependencies(value: str) -> list[str]:
    return [clean_text(part) for part in value.split(",") if clean_text(part)]


def _evidence_text(row: dict[str, Any]) -> str:
    parts = []
    for key, value in row.items():
        if value:
            parts.append(f"{key}: {value}")
    return clean_text(" | ".join(parts))[:1000]


def _stable_relation_id(
    source_file: str,
    sheet_name: str,
    row_number: int,
    source_label: str,
    target_label: str,
    relation_type: str,
) -> str:
    raw = f"{source_file}|{sheet_name}|{row_number}|{source_label}|{target_label}|{relation_type}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]
