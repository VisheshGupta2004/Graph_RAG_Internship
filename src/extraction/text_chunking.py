from __future__ import annotations

import hashlib
from typing import Any

from ..core.concepts import concept_id
from .html_parser import clean_text


RISK_TERMS = {
    "risk",
    "hazard",
    "danger",
    "failure",
    "consequence",
    "safety",
    "accident",
    "injury",
    "fire",
    "emergency",
}
PROCEDURE_TERMS = {
    "procedure",
    "sequence",
    "step",
    "start",
    "stop",
    "inspection",
    "checklist",
    "execute",
    "execution",
    "operation",
    "readiness",
}


def extract_semantic_chunks(nested_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Create concept-level chunks from the heading tree."""
    chunks: list[dict[str, Any]] = []
    _walk(nested_json, chunks, breadcrumb=[])
    return chunks


def prepare_chunks_for_storage(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize chunks and make them ready for TextChunk insertion."""
    prepared = []
    seen_ids: set[str] = set()

    for chunk in chunks:
        content = clean_text(chunk.get("content", ""))
        title = clean_text(chunk.get("title", ""))
        if not title or not content:
            continue

        stable_id = _stable_id(
            source_file=chunk["source_file"],
            section_id=chunk["section_id"],
            title=title,
            content=content,
        )
        if stable_id in seen_ids:
            continue
        seen_ids.add(stable_id)

        prepared.append(
            {
                "id": stable_id,
                "content": content,
                "title": title,
                "parent_title": chunk.get("parent_title") or "",
                "concept_id": concept_id(title),
                "section_id": chunk["section_id"],
                "source_file": chunk["source_file"],
                "type": chunk["type"],
                "metadata": {
                    "level": chunk["level"],
                    "breadcrumb": chunk["breadcrumb"],
                    "child_titles": chunk["child_titles"],
                    "content_length": len(content),
                },
            }
        )

    return prepared


def _walk(node: dict[str, Any], chunks: list[dict[str, Any]], breadcrumb: list[str]) -> None:
    current_breadcrumb = [*breadcrumb, node["title"]]
    content = _chunk_content(node)

    if node["level"] > 0 and node.get("content") and content:
        chunks.append(
            {
                "title": node["title"],
                "parent_title": node.get("parent_title"),
                "content": content,
                "section_id": node["section_id"],
                "concept_id": concept_id(node["title"]),
                "source_file": node["source_file"],
                "type": _infer_type(node["title"], content),
                "level": node["level"],
                "breadcrumb": current_breadcrumb,
                "child_titles": [child["title"] for child in node.get("children", [])],
            }
        )

    for child in node.get("children", []):
        _walk(child, chunks, current_breadcrumb)


def _chunk_content(node: dict[str, Any]) -> str:
    parts = [node["title"], node.get("content", "")]
    return clean_text("\n".join(part for part in parts if part))


def _infer_type(title: str, content: str) -> str:
    text = f"{title} {content}".lower()
    if any(term in text for term in RISK_TERMS):
        return "risk"
    if any(term in text for term in PROCEDURE_TERMS):
        return "procedure"
    return "concept"


def _stable_id(source_file: str, section_id: str, title: str, content: str) -> str:
    digest = hashlib.sha1(f"{source_file}|{section_id}|{title}|{content}".encode("utf-8")).hexdigest()
    return digest[:32]
