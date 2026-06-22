from __future__ import annotations

import json
from typing import Any

from ..core.config import GROQ_COMPRESSOR_MODEL
from ..providers.groq_provider import LLMProviderError, groq_chat_completion, parse_json_object


MAX_TEXT_EVIDENCE = 5
MAX_IMAGE_EVIDENCE = 2
MAX_RELATIONS = 6
MAX_EXCERPT_CHARS = 1000
MIN_EXCERPT_CHARS = 700


def compress_context(
    retrieval_context: dict[str, Any],
    use_llm: bool = True,
    allow_fallback: bool = True,
    model: str = GROQ_COMPRESSOR_MODEL,
) -> dict[str, Any]:
    """Compress retrieval context into compact, citation-preserving evidence."""
    deterministic = build_extractive_compact_context(retrieval_context)
    if not use_llm:
        return deterministic

    messages = [
        {
            "role": "system",
            "content": (
                "You are a context-compression agent for CHP industrial training. "
                "Return only valid JSON. Preserve citations, concept IDs, source files, and operational correctness. "
                "Do not add facts that are not present in the provided evidence."
            ),
        },
        {
            "role": "user",
            "content": (
                "Compress this retrieval evidence for a final grounded-answer agent. "
                "Keep at most 5 text evidence items, 2 image evidence items, and 6 relations. "
                "Use the exact JSON shape already provided and keep excerpts concise.\n\n"
                f"{json.dumps(deterministic, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        content = groq_chat_completion(
            messages=messages,
            model=model,
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=2500,
        )
        compressed = parse_json_object(content)
        return _normalize_compressed_context(compressed, deterministic, model)
    except Exception:
        if allow_fallback:
            deterministic["compression_metadata"]["mode"] = "extractive_fallback_after_llm_error"
            return deterministic
        raise


def build_extractive_compact_context(retrieval_context: dict[str, Any]) -> dict[str, Any]:
    query = retrieval_context.get("query", "")
    context = retrieval_context.get("context_for_llm_later", {})
    text_items = _dedupe_by_id(context.get("text_blocks", []))[:MAX_TEXT_EVIDENCE]
    image_items = _dedupe_by_id(context.get("image_blocks", []))[:MAX_IMAGE_EVIDENCE]
    relation_items = _dedupe_by_id(context.get("relation_blocks", []))[:MAX_RELATIONS]

    compact = {
        "query": query,
        "compact_context": {
            "key_text_evidence": [_compact_text_item(item) for item in text_items],
            "key_image_evidence": [_compact_image_item(item) for item in image_items],
            "key_relations": [_compact_relation_item(item) for item in relation_items],
            "source_references": _source_references(text_items, image_items),
            "coverage_notes": {
                "has_text_evidence": bool(text_items),
                "has_image_evidence": bool(image_items),
                "has_relation_trace": bool(relation_items),
                "weaknesses": _coverage_weaknesses(text_items, image_items, relation_items),
            },
        },
        "compression_metadata": {
            "mode": "extractive",
            "max_text_evidence": MAX_TEXT_EVIDENCE,
            "max_image_evidence": MAX_IMAGE_EVIDENCE,
            "max_relations": MAX_RELATIONS,
            "max_excerpt_chars": MAX_EXCERPT_CHARS,
        },
    }
    return compact


def _normalize_compressed_context(candidate: dict[str, Any], fallback: dict[str, Any], model: str) -> dict[str, Any]:
    evidence_keys = ["key_text_evidence", "key_image_evidence", "key_relations"]
    if "compact_context" not in candidate and all(key in candidate for key in evidence_keys):
        candidate = {
            "query": fallback.get("query", ""),
            "compact_context": {
                "key_text_evidence": candidate.get("key_text_evidence", []),
                "key_image_evidence": candidate.get("key_image_evidence", []),
                "key_relations": candidate.get("key_relations", []),
                "source_references": candidate.get("source_references"),
                "coverage_notes": candidate.get("coverage_notes"),
            },
        }
    if "compact_context" not in candidate:
        return fallback
    compact = candidate["compact_context"]
    if not all(key in compact for key in evidence_keys):
        return fallback
    compact["key_text_evidence"] = compact.get("key_text_evidence", [])[:MAX_TEXT_EVIDENCE]
    compact["key_image_evidence"] = compact.get("key_image_evidence", [])[:MAX_IMAGE_EVIDENCE]
    fallback_compact = fallback.get("compact_context", {})
    compact["key_relations"] = _traceable_relations(
        compact.get("key_relations", []),
        fallback_compact.get("key_relations", []),
    )[:MAX_RELATIONS]
    if not compact.get("source_references"):
        compact["source_references"] = fallback_compact.get("source_references", [])
    compact["coverage_notes"] = _coverage_notes_from_compact(compact)
    candidate.setdefault("query", fallback.get("query", ""))
    candidate["compression_metadata"] = {
        "mode": "groq",
        "model": model,
        "fallback_available": True,
    }
    return candidate


def _traceable_relations(candidate_relations: list[dict[str, Any]], fallback_relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not fallback_relations:
        return []
    by_id = {
        str(item.get("relation_id") or item.get("id")): item
        for item in fallback_relations
        if item.get("relation_id") or item.get("id")
    }
    traceable = []
    for item in candidate_relations:
        relation_id = str(item.get("relation_id") or item.get("id"))
        if relation_id in by_id:
            traceable.append(by_id[relation_id])
    return traceable or fallback_relations[:MAX_RELATIONS]


def _coverage_notes_from_compact(compact: dict[str, Any]) -> dict[str, Any]:
    text_items = compact.get("key_text_evidence", [])
    image_items = compact.get("key_image_evidence", [])
    relation_items = compact.get("key_relations", [])
    return {
        "has_text_evidence": bool(text_items),
        "has_image_evidence": bool(image_items),
        "has_relation_trace": bool(relation_items),
        "weaknesses": _coverage_weaknesses(text_items, image_items, relation_items),
    }


def _compact_text_item(item: dict[str, Any]) -> dict[str, Any]:
    content = str(item.get("content", "")).strip()
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "concept_id": item.get("concept_id"),
        "source_file": item.get("source_file"),
        "excerpt": _excerpt(content),
        "citation": _citation(item),
    }


def _compact_image_item(item: dict[str, Any]) -> dict[str, Any]:
    description = str(item.get("description", "")).strip()
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "concept_id": item.get("concept_id"),
        "source_file": item.get("source_file"),
        "description": _excerpt(description),
        "citation": _citation(item),
    }


def _compact_relation_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "relation_id": item.get("relation_id") or item.get("id"),
        "source_id": item.get("source_id"),
        "target_id": item.get("target_id"),
        "relation_type": item.get("relation_type"),
        "description": item.get("description"),
        "graph_relevance_score": item.get("graph_relevance_score"),
    }


def _source_references(text_items: list[dict[str, Any]], image_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for item in text_items + image_items:
        refs.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "source_file": item.get("source_file"),
                "concept_id": item.get("concept_id"),
            }
        )
    return refs


def _coverage_weaknesses(text_items: list[dict[str, Any]], image_items: list[dict[str, Any]], relation_items: list[dict[str, Any]]) -> list[str]:
    weaknesses = []
    if not text_items:
        weaknesses.append("No text evidence was retrieved.")
    if not image_items:
        weaknesses.append("No image or diagram description evidence was retrieved.")
    if not relation_items:
        weaknesses.append("No relation trace was retrieved; answer should rely mainly on text/image evidence.")
    return weaknesses


def _dedupe_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for item in items:
        key = item.get("id") or item.get("relation_id")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _excerpt(text: str) -> str:
    if len(text) <= MAX_EXCERPT_CHARS:
        return text
    cut = text[:MAX_EXCERPT_CHARS]
    last_stop = max(cut.rfind("."), cut.rfind(";"), cut.rfind("।"))
    if last_stop >= MIN_EXCERPT_CHARS:
        return cut[: last_stop + 1].strip()
    return cut.rstrip() + "..."


def _citation(item: dict[str, Any]) -> str:
    title = item.get("title") or "Untitled"
    concept_id = item.get("concept_id") or "unknown-concept"
    return f"[{title}, concept: {concept_id}]"
