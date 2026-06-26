from __future__ import annotations

import re
from collections import deque
from time import perf_counter
from typing import Any

from weaviate.classes.query import MetadataQuery

from ..core.config import CONCEPT_COLLECTION, IMAGE_COLLECTION, RELATION_COLLECTION, TEXT_COLLECTION
from ..embedding.service import embed_query
from ..storage.weaviate_setup import setup_weaviate


DEFAULT_TEXT_TOP_K = 5
DEFAULT_IMAGE_TOP_K = 3
DEFAULT_NODE_TOP_K = 5
DEFAULT_MAX_HOPS = 2
DEFAULT_RELATION_LIMIT = 30
DEFAULT_MAX_CONTEXT_TEXT = 8
DEFAULT_MAX_CONTEXT_IMAGES = 3
DEFAULT_MAX_CONTEXT_RELATIONS = 10

GENERIC_INSTRUCTION_TERMS = [
    "you are l1-ready",
    "you are l1 ready",
    "what you will learn",
    "course",
    "course complete",
    "assessment",
    "quick reference",
    "limits",
    "scoring guide",
    "self-declaration",
    "completion declaration",
    "your role as a trainee",
    "how to use this course",
]
OPERATIONAL_TERMS = {
    "belt", "drift", "misalignment", "fire", "hazard", "risk", "danger", "early", "signs",
    "transfer", "point", "conveyor", "grizzly", "hopper", "track", "arch", "formation",
    "coal", "flow", "wagon", "boiler", "bunker", "safety", "device", "pull", "cord",
    "idler", "pulley", "chute", "blockage", "spillage", "feeder", "observe", "trainee",
    "खतरा", "आग", "क्यों", "होता", "observe", "क्या", "belt", "fire",
}
RELATION_TYPE_WEIGHTS = {
    "depends_on": 0.9,
    "has_control_point": 0.85,
    "has_task": 0.75,
    "has_skill": 0.65,
    "has_swo": 0.6,
    "has_pwo": 0.55,
}


def retrieve_context(
    query: str,
    text_top_k: int = DEFAULT_TEXT_TOP_K,
    image_top_k: int = DEFAULT_IMAGE_TOP_K,
    node_top_k: int = DEFAULT_NODE_TOP_K,
    max_hops: int = DEFAULT_MAX_HOPS,
    relation_limit: int = DEFAULT_RELATION_LIMIT,
    max_context_text: int = DEFAULT_MAX_CONTEXT_TEXT,
    max_context_images: int = DEFAULT_MAX_CONTEXT_IMAGES,
    max_context_relations: int = DEFAULT_MAX_CONTEXT_RELATIONS,
    disable_graph: bool = False,
    debug_full_context: bool = False,
    client: Any | None = None,
) -> dict[str, Any]:
    """Retrieve text, image, node, and graph context without generating an answer."""
    timings: dict[str, float] = {}
    total_start = perf_counter()
    owns_client = client is None
    if client is None:
        step_start = perf_counter()
        client = setup_weaviate()
        timings["weaviate_setup_seconds"] = _elapsed_seconds(step_start)
    else:
        timings["weaviate_setup_seconds"] = 0.0

    try:
        step_start = perf_counter()
        query_vector = embed_query(query)
        timings["query_embedding_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        query_terms = _query_terms(query)
        timings["query_terms_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        raw_text_hits = _vector_search(client, TEXT_COLLECTION, query_vector, max(text_top_k * 4, text_top_k))
        timings["text_vector_search_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        raw_image_hits = _vector_search(client, IMAGE_COLLECTION, query_vector, max(image_top_k * 4, image_top_k))
        timings["image_vector_search_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        raw_node_hits = _vector_search(client, CONCEPT_COLLECTION, query_vector, max(node_top_k * 5, 20))
        timings["node_vector_search_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        node_hits = _rerank_node_hits(raw_node_hits, node_top_k)
        relation_seed_nodes = _relation_seed_node_hits(raw_node_hits, node_hits)
        timings["node_rerank_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        all_text = _fetch_all(client, TEXT_COLLECTION)
        timings["fetch_all_text_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        all_images = _fetch_all(client, IMAGE_COLLECTION)
        timings["fetch_all_images_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        all_nodes = _fetch_all(client, CONCEPT_COLLECTION)
        timings["fetch_all_nodes_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        all_relations = _fetch_all(client, RELATION_COLLECTION)
        timings["fetch_all_relations_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        text_hits = _rerank_evidence_hits(
            _merge_hits(raw_text_hits, _lexical_evidence_candidates(all_text, TEXT_COLLECTION, query_terms)),
            query_terms,
            text_top_k,
        )
        timings["text_lexical_merge_rerank_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        image_hits = _rerank_evidence_hits(
            _merge_hits(raw_image_hits, _lexical_evidence_candidates(all_images, IMAGE_COLLECTION, query_terms)),
            query_terms,
            image_top_k,
        )
        timings["image_lexical_merge_rerank_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        seed_concepts = _seed_concepts(text_hits, image_hits, node_hits + relation_seed_nodes)
        seed_scores = _seed_scores(text_hits, image_hits, node_hits, relation_seed_nodes)
        timings["seed_build_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        if disable_graph:
            expansion = {"concept_ids": set(seed_concepts), "nodes": [], "relations": [], "trace": [], "dropped_low_score_relations": []}
        else:
            expansion = _expand_graph(seed_concepts, all_nodes, all_relations, max_hops, relation_limit, seed_scores, query_terms)
        timings["graph_expansion_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        expanded_evidence = _expanded_evidence(
            expansion["concept_ids"],
            all_text,
            all_images,
            seed_text_ids={hit["id"] for hit in text_hits},
            seed_image_ids={hit["id"] for hit in image_hits},
        )
        expanded_evidence["text_chunks"] = _rerank_evidence_hits(expanded_evidence["text_chunks"], query_terms, len(expanded_evidence["text_chunks"]), graph_relevance=0.2)
        expanded_evidence["image_chunks"] = _rerank_evidence_hits(expanded_evidence["image_chunks"], query_terms, len(expanded_evidence["image_chunks"]), graph_relevance=0.2)
        timings["expanded_evidence_seconds"] = _elapsed_seconds(step_start)

        step_start = perf_counter()
        context, diagnostics = _build_context_blocks(
            text_hits,
            image_hits,
            node_hits,
            expansion["relations"],
            expanded_evidence,
            max_context_text=max_context_text,
            max_context_images=max_context_images,
            max_context_relations=max_context_relations,
            debug_full_context=debug_full_context,
        )
        timings["context_build_seconds"] = _elapsed_seconds(step_start)
        diagnostics["dropped_low_score_relations"] = expansion.get("dropped_low_score_relations", [])
        diagnostics["graph_disabled"] = disable_graph
        timings["total_retrieval_seconds"] = _elapsed_seconds(total_start)
        diagnostics["timings"] = timings

        return {
            "query": query,
            "seed_results": {
                "text_chunks": text_hits,
                "image_chunks": image_hits,
                "concept_nodes": node_hits,
            },
            "graph_expansion": {
                "max_hops": max_hops,
                "nodes": expansion["nodes"],
                "relations": expansion["relations"],
                "trace": expansion["trace"],
                "seed_relation_only_nodes": relation_seed_nodes,
            },
            "expanded_evidence": expanded_evidence,
            "context_for_llm_later": context,
            "retrieval_diagnostics": diagnostics,
        }
    finally:
        if owns_client:
            client.close()


def _elapsed_seconds(start: float) -> float:
    return round(perf_counter() - start, 3)


def _vector_search(client: Any, collection_name: str, query_vector: list[float], limit: int) -> list[dict[str, Any]]:
    collection = client.collections.get(collection_name)
    response = collection.query.near_vector(
        near_vector=query_vector,
        limit=limit,
        return_metadata=MetadataQuery(distance=True),
    )
    return [_format_hit(collection_name, item) for item in response.objects]


def _format_hit(collection_name: str, item: Any) -> dict[str, Any]:
    props = dict(item.properties)
    distance = getattr(item.metadata, "distance", None)
    score = None if distance is None else max(0.0, 1.0 - float(distance))
    if collection_name == TEXT_COLLECTION:
        object_id = props.get("chunk_id")
    elif collection_name == IMAGE_COLLECTION:
        object_id = props.get("image_id")
    elif collection_name == CONCEPT_COLLECTION:
        object_id = props.get("concept_id")
    else:
        object_id = props.get("relation_id")

    hit = {
        "collection": collection_name,
        "id": object_id,
        "concept_id": props.get("concept_id"),
        "title": props.get("title") or props.get("label"),
        "score": score,
        "vector_score": score,
        "rerank_score": score,
        "ranking_reasons": [],
        "generic_instruction_penalty": 0.0,
        "graph_relevance_score": 0.0,
        "distance": distance,
        "metadata": props.get("metadata", {}),
    }
    if collection_name == TEXT_COLLECTION:
        hit["content"] = props.get("content", "")
        hit["source_file"] = props.get("source_file")
        hit["section_id"] = props.get("section_id")
    elif collection_name == IMAGE_COLLECTION:
        hit["description"] = props.get("description", "")
        hit["source_file"] = props.get("source_file")
        hit["section_id"] = props.get("section_id")
    elif collection_name == CONCEPT_COLLECTION:
        hit["label"] = props.get("label")
        hit["concept_id"] = props.get("concept_id")
        hit["text_chunk_ids"] = props.get("text_chunk_ids", [])
        hit["image_ids"] = props.get("image_ids", [])
        hit["source_relation_ids"] = props.get("source_relation_ids", [])
        hit["target_relation_ids"] = props.get("target_relation_ids", [])
    return hit


def _rerank_node_hits(node_hits: list[dict[str, Any]], node_top_k: int) -> list[dict[str, Any]]:
    for hit in node_hits:
        metadata = hit.get("metadata") or {}
        retrieval_weight = float(metadata.get("retrieval_weight") or 0.35)
        base_score = float(hit.get("score") or 0.0)
        hit["retrieval_weight"] = retrieval_weight
        hit["weighted_score"] = base_score * retrieval_weight
        hit["rerank_score"] = hit["weighted_score"]
        hit["ranking_reasons"] = [f"node_weight={retrieval_weight}"]
    return sorted(node_hits, key=lambda hit: hit.get("weighted_score", 0.0), reverse=True)[:node_top_k]


def _relation_seed_node_hits(
    raw_node_hits: list[dict[str, Any]],
    displayed_node_hits: list[dict[str, Any]],
    limit: int = 3,
    min_score: float = 0.85,
) -> list[dict[str, Any]]:
    displayed_ids = {hit.get("concept_id") for hit in displayed_node_hits}
    seeds = []
    for hit in raw_node_hits:
        metadata = hit.get("metadata") or {}
        if metadata.get("has_evidence"):
            continue
        if hit.get("concept_id") in displayed_ids:
            continue
        if float(hit.get("score") or 0.0) < min_score:
            continue
        hit = dict(hit)
        hit["graph_seed_reason"] = "high_confidence_relation_only_node"
        seeds.append(hit)
        if len(seeds) >= limit:
            break
    return seeds


def _fetch_all(client: Any, collection_name: str, limit: int = 1000) -> list[dict[str, Any]]:
    collection = client.collections.get(collection_name)
    response = collection.query.fetch_objects(limit=limit)
    return [dict(item.properties) for item in response.objects]


def _seed_concepts(text_hits: list[dict[str, Any]], image_hits: list[dict[str, Any]], node_hits: list[dict[str, Any]]) -> set[str]:
    concepts = set()
    for hit in text_hits + image_hits + node_hits:
        concept_id = hit.get("concept_id")
        if concept_id:
            concepts.add(concept_id)
    return concepts


def _seed_scores(
    text_hits: list[dict[str, Any]],
    image_hits: list[dict[str, Any]],
    node_hits: list[dict[str, Any]],
    relation_seed_nodes: list[dict[str, Any]],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for hit in text_hits + image_hits + node_hits + relation_seed_nodes:
        concept_id = hit.get("concept_id")
        if not concept_id:
            continue
        scores[concept_id] = max(scores.get(concept_id, 0.0), float(hit.get("rerank_score") or hit.get("score") or 0.0))
    return scores


def _expand_graph(
    seed_concepts: set[str],
    all_nodes: list[dict[str, Any]],
    all_relations: list[dict[str, Any]],
    max_hops: int,
    relation_limit: int,
    seed_scores: dict[str, float],
    query_terms: set[str],
) -> dict[str, Any]:
    node_by_id = {node["concept_id"]: node for node in all_nodes}
    relation_by_id = {relation["relation_id"]: relation for relation in all_relations}
    adjacency = _build_adjacency(all_relations)
    visited_nodes = set(seed_concepts)
    visited_relations: set[str] = set()
    trace = []
    dropped_low_score_relations = []
    frontier = deque((concept_id, 0) for concept_id in seed_concepts)

    while frontier and len(visited_relations) < relation_limit:
        concept_id, depth = frontier.popleft()
        if depth >= max_hops:
            continue
        candidates = []
        for relation_id, neighbor_id, direction in adjacency.get(concept_id, []):
            relation = relation_by_id.get(relation_id)
            if not relation:
                continue
            score, reasons = _relation_score(relation, concept_id, neighbor_id, depth, node_by_id, seed_scores, query_terms)
            candidates.append((score, reasons, relation_id, neighbor_id, direction, relation))
        candidates.sort(key=lambda item: item[0], reverse=True)
        for score, reasons, relation_id, neighbor_id, direction, relation in candidates:
            if len(visited_relations) >= relation_limit:
                break
            min_score = 0.28 if depth == 0 else 0.42
            if score < min_score:
                dropped_low_score_relations.append({"relation_id": relation_id, "score": score, "reasons": reasons})
                continue
            if relation_id not in visited_relations:
                visited_relations.add(relation_id)
                trace.append(
                    {
                        "hop": depth + 1,
                        "from": concept_id,
                        "to": neighbor_id,
                        "direction": direction,
                        "relation_id": relation_id,
                        "relation_type": relation.get("relation_type"),
                        "graph_relevance_score": score,
                        "ranking_reasons": reasons,
                    }
                )
            if neighbor_id not in visited_nodes:
                visited_nodes.add(neighbor_id)
                if depth == 0 and score >= 0.5:
                    frontier.append((neighbor_id, depth + 1))

    return {
        "concept_ids": visited_nodes,
        "nodes": [_format_node(node_by_id[concept_id]) for concept_id in sorted(visited_nodes) if concept_id in node_by_id],
        "relations": sorted(
            [_format_relation(relation_by_id[relation_id], trace) for relation_id in visited_relations],
            key=lambda item: item.get("graph_relevance_score", 0.0),
            reverse=True,
        ),
        "trace": trace,
        "dropped_low_score_relations": dropped_low_score_relations[:20],
    }


def _build_adjacency(relations: list[dict[str, Any]]) -> dict[str, list[tuple[str, str, str]]]:
    adjacency: dict[str, list[tuple[str, str, str]]] = {}
    for relation in relations:
        source_id = relation.get("source_id")
        target_id = relation.get("target_id")
        relation_id = relation.get("relation_id")
        if not source_id or not target_id or not relation_id:
            continue
        adjacency.setdefault(source_id, []).append((relation_id, target_id, "out"))
        adjacency.setdefault(target_id, []).append((relation_id, source_id, "in"))
    return adjacency


def _expanded_evidence(
    concept_ids: set[str],
    all_text: list[dict[str, Any]],
    all_images: list[dict[str, Any]],
    seed_text_ids: set[str],
    seed_image_ids: set[str],
) -> dict[str, list[dict[str, Any]]]:
    text_chunks = [
        _format_text_object(obj)
        for obj in all_text
        if obj.get("concept_id") in concept_ids and obj.get("chunk_id") not in seed_text_ids
    ]
    image_chunks = [
        _format_image_object(obj)
        for obj in all_images
        if obj.get("concept_id") in concept_ids and obj.get("image_id") not in seed_image_ids
    ]
    return {
        "text_chunks": text_chunks,
        "image_chunks": image_chunks,
    }


def _build_context_blocks(
    text_hits: list[dict[str, Any]],
    image_hits: list[dict[str, Any]],
    node_hits: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    expanded_evidence: dict[str, list[dict[str, Any]]],
    max_context_text: int,
    max_context_images: int,
    max_context_relations: int,
    debug_full_context: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    diagnostics = {
        "dropped_generic_chunks": [],
        "dropped_duplicate_chunks": [],
        "dropped_low_score_relations": [],
        "final_context_counts": {},
    }
    text_items = _dedupe_items(text_hits + expanded_evidence["text_chunks"], diagnostics)
    image_items = _dedupe_items(image_hits + expanded_evidence["image_chunks"], diagnostics)
    text_items.sort(key=lambda item: item.get("rerank_score", item.get("score", 0.0)) or 0.0, reverse=True)
    image_items.sort(key=lambda item: item.get("rerank_score", item.get("score", 0.0)) or 0.0, reverse=True)
    relations = sorted(relations, key=lambda item: item.get("graph_relevance_score", 0.0), reverse=True)
    if not debug_full_context:
        text_items = text_items[:max_context_text]
        image_items = image_items[:max_context_images]
        relations = relations[:max_context_relations]
    source_references = []
    for item in text_items + image_items:
        source_references.append(
            {
                "collection": item["collection"],
                "id": item["id"],
                "title": item.get("title"),
                "source_file": item.get("source_file"),
                "section_id": item.get("section_id"),
                "concept_id": item.get("concept_id"),
            }
        )
    context = {
        "text_blocks": [
            {
                "id": item["id"],
                "title": item.get("title"),
                "concept_id": item.get("concept_id"),
                "source_file": item.get("source_file"),
                "content": item.get("content", ""),
                "rerank_score": item.get("rerank_score"),
                "ranking_reasons": item.get("ranking_reasons", []),
            }
            for item in text_items
        ],
        "image_blocks": [
            {
                "id": item["id"],
                "title": item.get("title"),
                "concept_id": item.get("concept_id"),
                "source_file": item.get("source_file"),
                "description": item.get("description", ""),
                "rerank_score": item.get("rerank_score"),
                "ranking_reasons": item.get("ranking_reasons", []),
            }
            for item in image_items
        ],
        "relation_blocks": relations,
        "seed_concept_nodes": node_hits,
        "source_references": source_references,
    }
    diagnostics["final_context_counts"] = {
        "text_blocks": len(context["text_blocks"]),
        "image_blocks": len(context["image_blocks"]),
        "relation_blocks": len(context["relation_blocks"]),
        "source_references": len(context["source_references"]),
    }
    return context, diagnostics


def _format_text_object(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "collection": TEXT_COLLECTION,
        "id": obj.get("chunk_id"),
        "concept_id": obj.get("concept_id"),
        "title": obj.get("title"),
        "content": obj.get("content", ""),
        "source_file": obj.get("source_file"),
        "section_id": obj.get("section_id"),
        "metadata": obj.get("metadata", {}),
    }


def _format_image_object(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "collection": IMAGE_COLLECTION,
        "id": obj.get("image_id"),
        "concept_id": obj.get("concept_id"),
        "title": obj.get("title"),
        "description": obj.get("description", ""),
        "source_file": obj.get("source_file"),
        "section_id": obj.get("section_id"),
        "metadata": obj.get("metadata", {}),
    }


def _format_node(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "collection": CONCEPT_COLLECTION,
        "id": obj.get("concept_id"),
        "concept_id": obj.get("concept_id"),
        "label": obj.get("label"),
        "text_chunk_ids": obj.get("text_chunk_ids", []),
        "image_ids": obj.get("image_ids", []),
        "source_relation_ids": obj.get("source_relation_ids", []),
        "target_relation_ids": obj.get("target_relation_ids", []),
        "metadata": obj.get("metadata", {}),
    }


def _query_terms(query: str) -> set[str]:
    tokens = set(re.findall(r"[\w\u0900-\u097F]+", query.lower()))
    return {token for token in tokens if len(token) > 2} | {token for token in tokens if token in OPERATIONAL_TERMS}


def _rerank_evidence_hits(
    hits: list[dict[str, Any]],
    query_terms: set[str],
    limit: int,
    graph_relevance: float = 0.0,
) -> list[dict[str, Any]]:
    for hit in hits:
        _score_evidence_hit(hit, query_terms, graph_relevance)
    return sorted(hits, key=lambda item: item.get("rerank_score", 0.0), reverse=True)[:limit]


def _score_evidence_hit(hit: dict[str, Any], query_terms: set[str], graph_relevance: float = 0.0) -> None:
    title_text = str(hit.get("title", "")).lower()
    text = " ".join(str(hit.get(field, "")) for field in ("title", "content", "description")).lower()
    hit_terms = set(re.findall(r"[\w\u0900-\u097F]+", text))
    title_terms = set(re.findall(r"[\w\u0900-\u097F]+", title_text))
    overlap = query_terms & hit_terms
    title_overlap = query_terms & title_terms
    operational_overlap = overlap & OPERATIONAL_TERMS
    metadata = hit.get("metadata") or {}
    chunk_type = str(hit.get("type") or metadata.get("type") or "").lower()
    base = float(hit.get("score") or hit.get("vector_score") or 0.0)
    reasons = []
    bonus = 0.0
    penalty = _generic_instruction_penalty(text)
    if overlap:
        bonus += min(0.16, 0.025 * len(overlap))
        reasons.append(f"query_overlap={len(overlap)}")
    if title_overlap:
        bonus += min(0.18, 0.06 * len(title_overlap))
        reasons.append(f"title_overlap={len(title_overlap)}")
    if operational_overlap:
        bonus += min(0.12, 0.04 * len(operational_overlap))
        reasons.append(f"operational_overlap={len(operational_overlap)}")
    if {"belt", "drift"} <= hit_terms and {"belt", "drift"} <= query_terms:
        bonus += 0.3
        reasons.append("exact_domain_phrase=belt_drift")
    if {"fire", "risk"} <= hit_terms and {"fire", "risk"} <= query_terms:
        bonus += 0.18
        reasons.append("exact_domain_phrase=fire_risk")
    if "risk" in chunk_type or "procedure" in chunk_type:
        bonus += 0.04
        reasons.append(f"type_boost={chunk_type}")
    if graph_relevance:
        bonus += graph_relevance
        reasons.append(f"graph_relevance={graph_relevance:.2f}")
    if penalty:
        reasons.append(f"generic_penalty={penalty:.2f}")
    hit["generic_instruction_penalty"] = penalty
    hit["graph_relevance_score"] = graph_relevance
    hit["ranking_reasons"] = reasons
    hit["rerank_score"] = max(0.0, base + bonus - penalty)


def _generic_instruction_penalty(text: str) -> float:
    penalty = 0.0
    for term in GENERIC_INSTRUCTION_TERMS:
        if term in text:
            penalty += 0.25
    return min(0.6, penalty)


def _merge_hits(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for hit in primary + secondary:
        key = (hit.get("collection"), hit.get("id"))
        if key not in merged or float(hit.get("score") or 0.0) > float(merged[key].get("score") or 0.0):
            merged[key] = hit
    return list(merged.values())


def _lexical_evidence_candidates(objects: list[dict[str, Any]], collection_name: str, query_terms: set[str], limit: int = 20) -> list[dict[str, Any]]:
    candidates = []
    for obj in objects:
        hit = _format_text_object(obj) if collection_name == TEXT_COLLECTION else _format_image_object(obj)
        text = " ".join(str(hit.get(field, "")) for field in ("title", "content", "description")).lower()
        terms = set(re.findall(r"[\w\u0900-\u097F]+", text))
        overlap = query_terms & terms
        if not overlap:
            continue
        title_terms = set(re.findall(r"[\w\u0900-\u097F]+", str(hit.get("title", "")).lower()))
        title_overlap = query_terms & title_terms
        score = 0.45 + min(0.25, 0.04 * len(overlap)) + min(0.25, 0.08 * len(title_overlap))
        if {"belt", "drift"} <= terms and {"belt", "drift"} <= query_terms:
            score += 0.3
        hit["score"] = min(score, 0.98)
        hit["vector_score"] = None
        hit["lexical_score"] = hit["score"]
        candidates.append(hit)
    candidates.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return candidates[:limit]


def _relation_score(
    relation: dict[str, Any],
    source_id: str,
    neighbor_id: str,
    depth: int,
    node_by_id: dict[str, dict[str, Any]],
    seed_scores: dict[str, float],
    query_terms: set[str],
) -> tuple[float, list[str]]:
    reasons = []
    seed_score = seed_scores.get(source_id, 0.5)
    hop_decay = 1.0 if depth == 0 else 0.65
    relation_type = relation.get("relation_type", "")
    type_weight = RELATION_TYPE_WEIGHTS.get(relation_type, 0.5)
    neighbor = node_by_id.get(neighbor_id, {})
    evidence_bonus = 0.2 if (neighbor.get("text_chunk_ids") or neighbor.get("image_ids")) else 0.0
    text = " ".join(
        str(value)
        for value in [
            relation.get("description", ""),
            relation.get("metadata", {}).get("source_label", ""),
            relation.get("metadata", {}).get("target_label", ""),
            relation.get("metadata", {}).get("evidence", ""),
        ]
    ).lower()
    relation_terms = set(re.findall(r"[\w\u0900-\u097F]+", text))
    overlap = len(query_terms & relation_terms)
    overlap_bonus = min(0.25, overlap * 0.04)
    score = (0.35 * seed_score) + (0.25 * type_weight) + evidence_bonus + overlap_bonus
    score *= hop_decay
    reasons.extend([
        f"seed={seed_score:.2f}",
        f"hop_decay={hop_decay:.2f}",
        f"type={relation_type}:{type_weight:.2f}",
    ])
    if evidence_bonus:
        reasons.append("endpoint_has_evidence")
    if overlap:
        reasons.append(f"query_overlap={overlap}")
    return score, reasons


def _format_relation(obj: dict[str, Any], trace: list[dict[str, Any]]) -> dict[str, Any]:
    trace_item = next((item for item in trace if item["relation_id"] == obj.get("relation_id")), {})
    return {
        "collection": RELATION_COLLECTION,
        "id": obj.get("relation_id"),
        "relation_id": obj.get("relation_id"),
        "source_id": obj.get("source_id"),
        "target_id": obj.get("target_id"),
        "relation_type": obj.get("relation_type"),
        "description": obj.get("description"),
        "graph_relevance_score": trace_item.get("graph_relevance_score", 0.0),
        "ranking_reasons": trace_item.get("ranking_reasons", []),
        "metadata": obj.get("metadata", {}),
    }


def _dedupe_items(items: list[dict[str, Any]], diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    seen_ids = set()
    seen_fingerprints = set()
    deduped = []
    for item in items:
        key = (item.get("collection"), item.get("id"))
        fingerprint = _fingerprint(item)
        if key in seen_ids or fingerprint in seen_fingerprints:
            diagnostics["dropped_duplicate_chunks"].append({"id": item.get("id"), "title": item.get("title")})
            continue
        if item.get("generic_instruction_penalty", 0.0) >= 0.5 and item.get("rerank_score", 0.0) < 0.85:
            diagnostics["dropped_generic_chunks"].append({"id": item.get("id"), "title": item.get("title")})
            continue
        seen_ids.add(key)
        seen_fingerprints.add(fingerprint)
        deduped.append(item)
    return deduped


def _fingerprint(item: dict[str, Any]) -> str:
    text = " ".join(str(item.get(field, "")) for field in ("title", "content", "description")).lower()
    tokens = re.findall(r"[\w\u0900-\u097F]+", text)
    return " ".join(tokens[:80])
