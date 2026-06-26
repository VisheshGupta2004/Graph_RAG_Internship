from __future__ import annotations

import json
from typing import Any

from ..core.config import GROQ_ANSWER_MAX_TOKENS, GROQ_ANSWER_MODEL
from ..providers.groq_provider import groq_chat_completion


def generate_grounded_answer(
    compressed_context: dict[str, Any],
    use_llm: bool = True,
    allow_fallback: bool = True,
    model: str = GROQ_ANSWER_MODEL,
) -> dict[str, Any]:
    """Generate a grounded answer from compressed context."""
    if not use_llm:
        return build_extractive_answer(compressed_context)

    language_instruction = _language_instruction(compressed_context.get("query", ""))
    messages = [
        {
            "role": "system",
            "content": (
                "You are a CHP industrial training assistant. Answer only from the compressed evidence. "
                f"{language_instruction} "
                "Cite each important claim inline using the provided citation strings. "
                "Separate course text/image evidence from graph relation context when relevant. "
                "Do not include a separate image gallery in the prose; image evidence is returned separately for the UI. "
                "If relation evidence is absent, say the answer is based mainly on course text/image evidence. "
                "Do not mention embeddings, reranking, retrieval internals, or model details."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(compressed_context, ensure_ascii=False),
        },
    ]
    try:
        answer = groq_chat_completion(messages=messages, model=model, temperature=0.1, max_tokens=GROQ_ANSWER_MAX_TOKENS)
        return _answer_payload(compressed_context, answer, mode="groq", model=model)
    except Exception as exc:
        if allow_fallback:
            print(f"[answer generation] falling back to extractive answer: {exc}", flush=True)
            fallback = build_extractive_answer(compressed_context)
            fallback["answer_metadata"]["mode"] = "extractive_fallback_after_llm_error"
            return fallback
        raise


def build_extractive_answer(compressed_context: dict[str, Any]) -> dict[str, Any]:
    query = compressed_context.get("query", "")
    compact = compressed_context.get("compact_context", {})
    text_items = compact.get("key_text_evidence", [])
    image_items = compact.get("key_image_evidence", [])
    relation_items = compact.get("key_relations", [])
    notes = compact.get("coverage_notes", {})

    lines = [f"Query: {query}", ""]
    if notes.get("has_relation_trace") is False:
        lines.append("This draft is based mainly on retrieved course text/image evidence; no supporting relation trace was retrieved.")
        lines.append("")

    if text_items:
        lines.append("Key course evidence:")
        for item in text_items[:5]:
            lines.append(f"- {item.get('excerpt', '')} {item.get('citation', '')}")
    if image_items:
        lines.append("")
        lines.append("Relevant diagram/image evidence:")
        for item in image_items[:2]:
            lines.append(f"- {item.get('description', '')} {item.get('citation', '')}")
    if relation_items:
        lines.append("")
        lines.append("Relevant graph relation context:")
        for item in relation_items[:6]:
            lines.append(f"- {item.get('source_id')} --{item.get('relation_type')}--> {item.get('target_id')}: {item.get('description')}")

    return _answer_payload(compressed_context, "\n".join(lines).strip(), mode="extractive", model=None)


def _answer_payload(compressed_context: dict[str, Any], answer: str, mode: str, model: str | None) -> dict[str, Any]:
    compact = compressed_context.get("compact_context", {})
    retrieved_images = _retrieved_images(compact.get("key_image_evidence", []))
    citations = compact.get("source_references", [])
    coverage_notes = compact.get("coverage_notes", {})
    language = _language_signal(compressed_context.get("query", ""))
    return {
        "query": compressed_context.get("query", ""),
        "answer": answer,
        "retrieved_images": retrieved_images,
        "citations": citations,
        "coverage_notes": coverage_notes,
        "ui_response": {
            "answer_text": answer,
            "retrieved_images": retrieved_images,
            "citations": citations,
            "coverage_notes": coverage_notes,
            "language": language,
        },
        "answer_metadata": {
            "mode": mode,
            "model": model,
            "uses_only_compressed_context": True,
            "image_evidence_count": len(retrieved_images),
            "language": language,
        },
    }


def _retrieved_images(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    images = []
    for item in items:
        images.append(
            {
                "image_id": item.get("id") or item.get("image_id"),
                "title": item.get("title"),
                "concept_id": item.get("concept_id"),
                "source_file": item.get("source_file"),
                "description": item.get("description"),
                "citation": item.get("citation"),
                "display_type": "image_description",
            }
        )
    return images


def _language_signal(query: str) -> str:
    if any("\u0900" <= char <= "\u097f" for char in query):
        return "hi-en"
    return "en"


def _language_instruction(query: str) -> str:
    if _language_signal(query) == "hi-en":
        return (
            "The user query contains Hindi/Devanagari. Answer mainly in Hindi, "
            "preserving common plant terms such as belt drift, fire risk, BSW, EPC, conveyor, and trainee in English where natural."
        )
    return "Answer in English, preserving Hindi terms only when they appear in cited evidence."
