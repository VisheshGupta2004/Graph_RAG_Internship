# Understand The Backend Code

This guide explains the restructured backend for the Weaviate-only CHP Graph RAG MVP.

The backend is organized by lifecycle:

```text
one-time indexing:
  extraction -> graph -> embedding -> storage

per-query runtime:
  retrieval -> answering -> server/api

support:
  core -> providers -> cli -> eval
```

Existing public commands still work through thin wrappers:

```bash
python -m src.run_ingestion
python -m src.run_retrieval
python -m src.run_answer
python -m src.answer_smoke_test
python -m src.retrieval_smoke_test
python -m src.vector_smoke_test
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

## Package Map

```text
src/core
```

Configuration and shared identifiers.

- `config.py`: paths, collection names, model names, Weaviate settings, CORS settings.
- `concepts.py`: deterministic concept ID normalization.

```text
src/extraction
```

HTML/course extraction and ingestion orchestration.

- `html_parser.py`: parses HTML, headings, tables, SVG text labels, and iCard templates.
- `text_chunking.py`: creates topic-level `TextChunk` objects.
- `image_extraction.py`: extracts SVG/image diagram metadata and reconstructs SVGs by image ID.
- `pipeline.py`: orchestrates ingestion from HTML + Excel relations into storage-ready objects.

```text
src/graph
```

Graph-like build steps.

- `relations.py`: reads `Data/CHP WRCF.xlsx` and creates `RelationChunk` edges.
- `concept_nodes.py`: creates `ConceptNode` records from text/image concepts and relation endpoints.

```text
src/embedding
```

Local multilingual embedding service.

- `service.py`: embeds text chunks, image descriptions, concept nodes, and queries with `intfloat/multilingual-e5-small`.

```text
src/storage
```

Weaviate schema, inserts, and validation.

- `weaviate_setup.py`: connects to local Weaviate and creates collections.
- `repositories.py`: inserts `TextChunk`, `ImageChunk`, `RelationChunk`, and `ConceptNode`.
- `validation.py`: validates generated object completeness and embedding summaries.

```text
src/retrieval
```

Per-query retrieval runtime.

- `service.py`: embeds the query, retrieves text/images/nodes, reranks evidence, expands relations up to 2 hops, and packages bounded context.
- `__init__.py`: re-exports `retrieve_context` and retrieval constants.

```text
src/answering
```

Answer-layer runtime.

- `compression.py`: compresses retrieval context while preserving citations and coverage notes.
- `generator.py`: generates grounded answers from compressed context with Groq or extractive fallback.

```text
src/providers
```

External model providers.

- `groq_provider.py`: Groq chat completions, JSON parsing, API key lookup, and speech-to-text transcription.

```text
src/server
```

FastAPI implementation.

- `app.py`: defines `/health`, `/chat`, `/transcribe`, and `/images/{image_id}.svg`.
- `src/api.py`: compatibility entrypoint that exposes `app` for `uvicorn src.api:app`.

```text
src/cli
```

CLI implementations used by top-level wrappers.

- `run_ingestion.py`
- `run_retrieval.py`
- `run_answer.py`

```text
src/eval
```

Smoke tests and default prompts.

- `test_prompts.py`
- `vector_smoke_test.py`
- `retrieval_smoke_test.py`
- `answer_smoke_test.py`

## Main Data Flow

Ingestion/indexing:

```text
HTML files
  -> extraction.html_parser
  -> extraction.text_chunking
  -> extraction.image_extraction
  -> graph.relations from Excel
  -> graph.concept_nodes
  -> optional embedding.service vectors
  -> storage.repositories into Weaviate
  -> storage.validation report
```

Runtime query:

```text
user query
  -> retrieval.retrieve_context
  -> answering.compress_context
  -> answering.generate_grounded_answer
  -> server.app simplified UI response
```

Voice input:

```text
browser audio upload
  -> POST /transcribe
  -> providers.groq_provider.groq_transcribe_audio
  -> transcript text
```

Diagram display:

```text
retrieved image_id
  -> GET /images/{image_id}.svg
  -> extraction.image_extraction.find_svg_by_image_id
  -> original inline SVG from Data/*.html
```

## Commands

Generate artifacts only:

```bash
python -m src.run_ingestion
```

Store with embeddings:

```bash
python -m src.run_ingestion --store --embed --reset-text --reset-images --reset-relations --reset-concepts
```

Run retrieval smoke tests:

```bash
python -m src.retrieval_smoke_test
```

Run vector smoke tests:

```bash
python -m src.vector_smoke_test
```

Run offline answer smoke tests:

```bash
python -m src.answer_smoke_test
```

Run API:

```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

Serve frontend:

```bash
cd frontend
python -m http.server 5173
```

## Verification After Restructure

Verified after moving to packages:

- `python -m compileall src`
- `python -m src.run_ingestion`
- `python -m src.answer_smoke_test`
- `python -m src.retrieval_smoke_test`
- `python -m src.vector_smoke_test`
- FastAPI `/health`, empty `/chat`, missing-file `/transcribe`, and SVG image endpoint checks.

## Mental Model

```text
TextChunk = evidence from HTML text
ImageChunk = evidence from diagrams
RelationChunk = graph edge from Excel
ConceptNode = graph node from shared concept/relation IDs
concept_id = shared graph/node key
section_id = exact heading attachment key
```

The source tree now separates one-time indexing code from every-query runtime code. The behavior and command surface are intentionally unchanged.
