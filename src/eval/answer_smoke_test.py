from __future__ import annotations

import json
import sys
from pathlib import Path

from ..answering.compression import compress_context
from ..answering.generator import generate_grounded_answer
from ..core.config import ANSWER_ARTIFACTS_DIR, RETRIEVAL_ARTIFACTS_DIR
from ..retrieval import retrieve_context
from .test_prompts import TEST_PROMPTS


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ANSWER_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for index, prompt in enumerate(TEST_PROMPTS, start=1):
        retrieval_path = RETRIEVAL_ARTIFACTS_DIR / f"context_prompt_{index}.json"
        retrieval_context = _read_or_retrieve(retrieval_path, prompt)
        compressed = compress_context(retrieval_context, use_llm=False)
        answer = generate_grounded_answer(compressed, use_llm=False)
        compressed_path = ANSWER_ARTIFACTS_DIR / f"compressed_prompt_{index}.json"
        answer_path = ANSWER_ARTIFACTS_DIR / f"answer_prompt_{index}.json"
        _write_json(compressed_path, compressed)
        _write_json(answer_path, answer)
        summary = _summary(index, prompt, retrieval_context, compressed, answer)
        summaries.append(summary)
        print(f"[{index}] ok={summary['passed']} compressed_smaller={summary['compressed_smaller']} citations={summary['citations']}")
    _write_json(ANSWER_ARTIFACTS_DIR / "answer_smoke_summary.json", summaries)
    if not all(item["passed"] for item in summaries):
        raise SystemExit(1)


def _read_or_retrieve(path: Path, prompt: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    context = retrieve_context(prompt)
    _write_json(path, context)
    return context


def _summary(index: int, prompt: str, retrieval_context: dict, compressed: dict, answer: dict) -> dict:
    retrieval_size = len(json.dumps(retrieval_context, ensure_ascii=False))
    compressed_size = len(json.dumps(compressed, ensure_ascii=False))
    compact = compressed.get("compact_context", {})
    citations = len(answer.get("citations", []))
    passed = (
        compressed_size < retrieval_size
        and bool(compact.get("key_text_evidence") or compact.get("key_image_evidence"))
        and citations > 0
        and answer.get("answer_metadata", {}).get("uses_only_compressed_context") is True
    )
    return {
        "index": index,
        "prompt": prompt,
        "passed": passed,
        "compressed_smaller": compressed_size < retrieval_size,
        "retrieval_size": retrieval_size,
        "compressed_size": compressed_size,
        "citations": citations,
        "has_relation_trace": compact.get("coverage_notes", {}).get("has_relation_trace"),
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
