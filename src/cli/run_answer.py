from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..answering.compression import compress_context
from ..answering.generator import generate_grounded_answer
from ..core.config import ANSWER_ARTIFACTS_DIR, RETRIEVAL_ARTIFACTS_DIR
from ..retrieval import retrieve_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress retrieval context and generate a grounded answer.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--retrieval", default=str(RETRIEVAL_ARTIFACTS_DIR / "context.json"))
    parser.add_argument("--skip-retrieval", action="store_true", help="Require the retrieval JSON to already exist.")
    parser.add_argument("--save-compressed", default=str(ANSWER_ARTIFACTS_DIR / "compressed.json"))
    parser.add_argument("--out", default=str(ANSWER_ARTIFACTS_DIR / "answer.json"))
    parser.add_argument("--offline", action="store_true", help="Use deterministic extractive compression/answering without Groq.")
    parser.add_argument("--no-fallback", action="store_true", help="Fail instead of falling back to extractive mode on LLM errors.")
    args = parser.parse_args()

    retrieval_path = Path(args.retrieval)
    if retrieval_path.exists():
        retrieval_context = _read_json(retrieval_path)
    elif args.skip_retrieval:
        raise FileNotFoundError(f"Retrieval context not found: {retrieval_path}")
    else:
        retrieval_context = retrieve_context(args.query)
        _write_json(retrieval_path, retrieval_context)

    use_llm = not args.offline
    allow_fallback = not args.no_fallback
    compressed = compress_context(retrieval_context, use_llm=use_llm, allow_fallback=allow_fallback)
    answer = generate_grounded_answer(compressed, use_llm=use_llm, allow_fallback=allow_fallback)

    compressed_path = Path(args.save_compressed)
    answer_path = Path(args.out)
    _write_json(compressed_path, compressed)
    _write_json(answer_path, answer)

    retrieval_size = len(json.dumps(retrieval_context, ensure_ascii=False))
    compressed_size = len(json.dumps(compressed, ensure_ascii=False))
    _safe_print(f"Query: {args.query}")
    _safe_print(f"Retrieval context: {retrieval_path}")
    _safe_print(f"Compressed context: {compressed_path}")
    _safe_print(f"Answer: {answer_path}")
    _safe_print(f"Compression mode: {compressed.get('compression_metadata', {}).get('mode')}")
    _safe_print(f"Answer mode: {answer.get('answer_metadata', {}).get('mode')}")
    _safe_print(f"Compressed smaller than retrieval: {compressed_size < retrieval_size}")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_print(value: str) -> None:
    try:
        print(value)
    except UnicodeEncodeError:
        print(value.encode("ascii", errors="backslashreplace").decode("ascii"))


if __name__ == "__main__":
    main()
