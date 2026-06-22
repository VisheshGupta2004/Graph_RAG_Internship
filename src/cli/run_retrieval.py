from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..core.config import RETRIEVAL_ARTIFACTS_DIR
from ..eval.test_prompts import TEST_PROMPTS
from ..retrieval import (
    DEFAULT_IMAGE_TOP_K,
    DEFAULT_MAX_HOPS,
    DEFAULT_MAX_CONTEXT_IMAGES,
    DEFAULT_MAX_CONTEXT_RELATIONS,
    DEFAULT_MAX_CONTEXT_TEXT,
    DEFAULT_NODE_TOP_K,
    DEFAULT_RELATION_LIMIT,
    DEFAULT_TEXT_TOP_K,
    retrieve_context,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve a Graph RAG context package without LLM generation.")
    parser.add_argument("--query", required=True, help="User query to retrieve context for.")
    parser.add_argument("--out", default=str(RETRIEVAL_ARTIFACTS_DIR / "context.json"), help="Output JSON path.")
    parser.add_argument("--text-top-k", type=int, default=DEFAULT_TEXT_TOP_K)
    parser.add_argument("--image-top-k", type=int, default=DEFAULT_IMAGE_TOP_K)
    parser.add_argument("--node-top-k", type=int, default=DEFAULT_NODE_TOP_K)
    parser.add_argument("--max-hops", type=int, default=DEFAULT_MAX_HOPS)
    parser.add_argument("--relation-limit", type=int, default=DEFAULT_RELATION_LIMIT)
    parser.add_argument("--max-context-text", type=int, default=DEFAULT_MAX_CONTEXT_TEXT)
    parser.add_argument("--max-context-images", type=int, default=DEFAULT_MAX_CONTEXT_IMAGES)
    parser.add_argument("--max-context-relations", type=int, default=DEFAULT_MAX_CONTEXT_RELATIONS)
    parser.add_argument("--disable-graph", action="store_true")
    parser.add_argument("--debug-full-context", action="store_true")
    parser.add_argument("--write-test-prompts", action="store_true", help="Write the default retrieval test prompts artifact.")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.write_test_prompts:
        _write_json(RETRIEVAL_ARTIFACTS_DIR / "test_prompts.json", TEST_PROMPTS)

    context = retrieve_context(
        query=args.query,
        text_top_k=args.text_top_k,
        image_top_k=args.image_top_k,
        node_top_k=args.node_top_k,
        max_hops=args.max_hops,
        relation_limit=args.relation_limit,
        max_context_text=args.max_context_text,
        max_context_images=args.max_context_images,
        max_context_relations=args.max_context_relations,
        disable_graph=args.disable_graph,
        debug_full_context=args.debug_full_context,
    )
    _write_json(out_path, context)

    print(f"Query: {args.query}")
    print(f"Text hits: {len(context['seed_results']['text_chunks'])}")
    print(f"Image hits: {len(context['seed_results']['image_chunks'])}")
    print(f"Node hits: {len(context['seed_results']['concept_nodes'])}")
    print(f"Expanded nodes: {len(context['graph_expansion']['nodes'])}")
    print(f"Expanded relations: {len(context['graph_expansion']['relations'])}")
    print(f"Expanded text evidence: {len(context['expanded_evidence']['text_chunks'])}")
    print(f"Expanded image evidence: {len(context['expanded_evidence']['image_chunks'])}")
    print(f"LLM text blocks: {len(context['context_for_llm_later']['text_blocks'])}")
    print(f"LLM image blocks: {len(context['context_for_llm_later']['image_blocks'])}")
    print(f"LLM relation blocks: {len(context['context_for_llm_later']['relation_blocks'])}")
    print(f"Output: {out_path}")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
