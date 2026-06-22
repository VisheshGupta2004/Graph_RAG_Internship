from __future__ import annotations

import sys
from typing import Any

from weaviate.classes.query import Filter

from ..core.config import CONCEPT_COLLECTION, IMAGE_COLLECTION, TEXT_COLLECTION
from ..embedding.service import embed_query
from ..storage.weaviate_setup import setup_weaviate


SMOKE_QUERIES = [
    ("text_en", TEXT_COLLECTION, "why belt drift is dangerous"),
    ("text_hi", TEXT_COLLECTION, "belt drift से fire risk क्यों होता है"),
    ("image_en", IMAGE_COLLECTION, "coal flow from wagon to boiler diagram"),
    ("node_en", CONCEPT_COLLECTION, "belt conveyor operation hazards"),
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    client = setup_weaviate()
    try:
        for name, collection_name, query in SMOKE_QUERIES:
            print(f"\n[{name}] {query}")
            vector = embed_query(query)
            collection = client.collections.get(collection_name)
            response = collection.query.near_vector(near_vector=vector, limit=3)
            for item in response.objects:
                props = item.properties
                concept_id = props.get("concept_id")
                concept_found = _concept_exists(client, concept_id) if concept_id else False
                object_id = props.get("chunk_id") or props.get("image_id") or props.get("concept_id")
                title = props.get("title") or props.get("label")
                print(f"- {collection_name} {object_id} | {title} | concept={concept_id} | concept_found={concept_found}")
    finally:
        client.close()


def _concept_exists(client: Any, concept_id: str) -> bool:
    concepts = client.collections.get(CONCEPT_COLLECTION)
    response = concepts.query.fetch_objects(
        filters=Filter.by_property("concept_id").equal(concept_id),
        limit=1,
    )
    return bool(response.objects)


if __name__ == "__main__":
    main()
