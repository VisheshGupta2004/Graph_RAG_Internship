from __future__ import annotations

import json
import sys
from pathlib import Path

from ..core.config import RETRIEVAL_ARTIFACTS_DIR
from ..retrieval import DEFAULT_MAX_CONTEXT_IMAGES, DEFAULT_MAX_CONTEXT_RELATIONS, DEFAULT_MAX_CONTEXT_TEXT, retrieve_context
from .test_prompts import TEST_PROMPTS


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    RETRIEVAL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(RETRIEVAL_ARTIFACTS_DIR / "test_prompts.json", TEST_PROMPTS)
    summaries = []
    for index, prompt in enumerate(TEST_PROMPTS, start=1):
        context = retrieve_context(prompt)
        output_path = RETRIEVAL_ARTIFACTS_DIR / f"context_prompt_{index}.json"
        _write_json(output_path, context)
        summary = _validate_context(index, prompt, context, output_path)
        summaries.append(summary)
        print(
            f"[{index}] ok={summary['passed']} text={summary['text_blocks']} "
            f"images={summary['image_blocks']} relations={summary['relations']} trace={summary['trace']} "
            f"out={output_path}"
        )
    _write_json(RETRIEVAL_ARTIFACTS_DIR / "smoke_summary.json", summaries)
    if not all(summary["passed"] for summary in summaries):
        raise SystemExit(1)


def _validate_context(index: int, prompt: str, context: dict, output_path: Path) -> dict:
    text_blocks = len(context["context_for_llm_later"]["text_blocks"])
    image_blocks = len(context["context_for_llm_later"]["image_blocks"])
    relation_blocks = len(context["context_for_llm_later"]["relation_blocks"])
    trace = context["graph_expansion"]["trace"]
    max_seen_hop = max((item["hop"] for item in trace), default=0)
    titles = [str(item.get("title", "")).lower() for item in context["context_for_llm_later"]["text_blocks"]]
    quality_checks = _quality_checks(index, titles, context)
    passed = (
        bool(text_blocks or image_blocks)
        and max_seen_hop <= context["graph_expansion"]["max_hops"]
        and text_blocks <= DEFAULT_MAX_CONTEXT_TEXT
        and image_blocks <= DEFAULT_MAX_CONTEXT_IMAGES
        and relation_blocks <= DEFAULT_MAX_CONTEXT_RELATIONS
        and all(quality_checks.values())
        and "answer" not in context
    )
    return {
        "index": index,
        "prompt": prompt,
        "output": str(output_path),
        "passed": passed,
        "text_blocks": text_blocks,
        "image_blocks": image_blocks,
        "relations": len(context["graph_expansion"]["relations"]),
        "relation_blocks": relation_blocks,
        "trace": len(trace),
        "max_seen_hop": max_seen_hop,
        "seed_relation_only_nodes": len(context["graph_expansion"].get("seed_relation_only_nodes", [])),
        "quality_checks": quality_checks,
        "diagnostics": context.get("retrieval_diagnostics", {}),
    }


def _quality_checks(index: int, titles: list[str], context: dict) -> dict[str, bool]:
    joined = " | ".join(titles)
    checks = {"bounded_context": True}
    if index == 1:
        checks["belt_drift_before_generic"] = bool(titles and ("belt drift" in joined or "misalignment" in joined))
        checks["generic_not_first"] = not (titles and ("you are l1-ready" in titles[0] or "you are l1 ready" in titles[0]))
    if index == 2:
        checks["hindi_or_fire_belt_context"] = "belt drift" in joined or "fire" in joined or "खतरा" in joined
    if index == 3:
        checks["coal_flow_diagram"] = len(context["context_for_llm_later"]["image_blocks"]) >= 1
        checks["relation_trace_present"] = len(context["graph_expansion"]["trace"]) >= 1
    if index == 5:
        checks["transfer_or_hazard"] = "transfer" in joined or "hazard" in joined or "safety" in joined
        checks["limits_not_in_context"] = "limits" not in joined and "⚠ limits" not in joined
    return checks


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
