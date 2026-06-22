from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..core.config import ARTIFACTS_DIR, DATA_DIR
from ..extraction.pipeline import ingest_html_file, ingest_html_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Build text and image chunks from CHP HTML training files.")
    parser.add_argument(
        "files",
        nargs="*",
        help="HTML files to ingest. Defaults to all *.html files under Data.",
    )
    parser.add_argument("--store", action="store_true", help="Insert prepared objects into Weaviate.")
    parser.add_argument("--embed", action="store_true", help="Generate local multilingual embeddings for TextChunk and ImageChunk storage.")
    parser.add_argument(
        "--reset-text",
        action="store_true",
        help="Drop and recreate TextChunk before storing. ImageChunk and RelationChunk are kept.",
    )
    parser.add_argument(
        "--reset-images",
        action="store_true",
        help="Drop and recreate ImageChunk before storing. TextChunk and RelationChunk are kept.",
    )
    parser.add_argument(
        "--reset-relations",
        action="store_true",
        help="Drop and recreate RelationChunk before storing. TextChunk and ImageChunk are kept.",
    )
    parser.add_argument(
        "--reset-concepts",
        action="store_true",
        help="Drop and recreate ConceptNode before storing. Other collections are kept.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ARTIFACTS_DIR),
        help="Directory for nested JSON and chunk artifacts.",
    )
    args = parser.parse_args()
    if (args.reset_text or args.reset_images or args.reset_relations or args.reset_concepts) and not args.store:
        parser.error("--reset-* options can only be used with --store")

    if args.reset_text:
        from ..storage.weaviate_setup import reset_text_collection

        reset_text_collection()
    if args.reset_images:
        from ..storage.weaviate_setup import reset_image_collection

        reset_image_collection()
    if args.reset_relations:
        from ..storage.weaviate_setup import reset_relation_collection

        reset_relation_collection()
    if args.reset_concepts:
        from ..storage.weaviate_setup import reset_concept_collection

        reset_concept_collection()

    files = [Path(file) for file in args.files] if args.files else sorted(DATA_DIR.glob("*.html"))
    result = ingest_html_files(files, store=args.store, embed=args.embed)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "nested_structure.json", result["nested_json"])
    _write_json(out_dir / "semantic_chunks.json", result["semantic_chunks"])
    _write_json(out_dir / "image_chunks.json", result["image_chunks"])
    _write_json(out_dir / "relation_chunks.json", result["relation_chunks"])
    _write_json(out_dir / "textchunk_objects.json", result["storage_objects"])
    _write_json(out_dir / "imagechunk_objects.json", result["image_storage_objects"])
    _write_json(out_dir / "relationchunk_objects.json", result["relation_storage_objects"])
    _write_json(out_dir / "conceptnode_objects.json", result["concept_storage_objects"])
    _write_json(out_dir / "validation_report.json", result["validation_report"])
    _write_per_file_artifacts(files, out_dir, result["relation_chunks"], result["relation_storage_objects"], result["concept_storage_objects"])

    print(f"Processed files: {len(files)}")
    print(f"Semantic chunks: {len(result['semantic_chunks'])}")
    print(f"Image chunks: {len(result['image_chunks'])}")
    print(f"Relation chunks: {len(result['relation_chunks'])}")
    print(f"Storage objects: {len(result['storage_objects'])}")
    print(f"Image storage objects: {len(result['image_storage_objects'])}")
    print(f"Relation storage objects: {len(result['relation_storage_objects'])}")
    print(f"Concept node objects: {len(result['concept_storage_objects'])}")
    print(f"Embeddings enabled: {result['validation_report']['embeddings']['enabled']}")
    print(f"Validation passed: {result['validation_report']['passed']}")
    print(f"Artifacts: {out_dir}")
    if "weaviate" in result:
        print(f"Weaviate text insert attempted: {result['weaviate']['text']['attempted']}")
        print(f"Weaviate text insert failed: {result['weaviate']['text']['failed']}")
        print(f"Weaviate image insert attempted: {result['weaviate']['images']['attempted']}")
        print(f"Weaviate image insert failed: {result['weaviate']['images']['failed']}")
        print(f"Weaviate relation insert attempted: {result['weaviate']['relations']['attempted']}")
        print(f"Weaviate relation insert failed: {result['weaviate']['relations']['failed']}")
        print(f"Weaviate concept insert attempted: {result['weaviate']['concepts']['attempted']}")
        print(f"Weaviate concept insert failed: {result['weaviate']['concepts']['failed']}")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_per_file_artifacts(
    files: list[Path],
    out_dir: Path,
    relation_chunks: list[dict],
    relation_objects: list[dict],
    concept_objects: list[dict],
) -> None:
    per_file_dir = out_dir / "by_file"
    per_file_dir.mkdir(parents=True, exist_ok=True)

    for file_path in files:
        result = ingest_html_file(file_path, store=False)
        module = {
            "source_file": file_path.name,
            "nested_json": result["nested_json"],
            "text_chunks": result["semantic_chunks"],
            "image_chunks": result["image_chunks"],
            "relations": _relations_for_module(result, relation_chunks),
            "textchunk_objects": result["storage_objects"],
            "imagechunk_objects": result["image_storage_objects"],
            "relationchunk_objects": _relations_for_module(result, relation_objects),
            "conceptnode_objects": _concepts_for_module(result, concept_objects),
        }
        _write_json(per_file_dir / f"{file_path.stem}.json", module)


def _relations_for_module(result: dict, relations: list[dict]) -> list[dict]:
    concept_ids = {chunk.get("concept_id") for chunk in result["storage_objects"]}
    concept_ids.update(image.get("concept_id") for image in result["image_storage_objects"])
    concept_ids.discard(None)
    return [
        relation
        for relation in relations
        if relation.get("source_id") in concept_ids or relation.get("target_id") in concept_ids
    ]


def _concepts_for_module(result: dict, concepts: list[dict]) -> list[dict]:
    concept_ids = {chunk.get("concept_id") for chunk in result["storage_objects"]}
    concept_ids.update(image.get("concept_id") for image in result["image_storage_objects"])
    concept_ids.discard(None)
    return [concept for concept in concepts if concept.get("concept_id") in concept_ids]


if __name__ == "__main__":
    main()
