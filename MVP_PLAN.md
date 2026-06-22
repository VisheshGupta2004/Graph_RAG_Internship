# Weaviate-Only Graph RAG MVP Plan

## 1. MVP Goal

Build a Phase-1 Graph RAG MVP for CHP industrial training data using **Weaviate only**.

The MVP validates:

- HTML training document ingestion
- hierarchical structure extraction
- topic-level text chunking
- diagram/image attachment to headings
- Excel relation ingestion
- concept-node graph alignment
- multilingual vector retrieval over text, diagrams, and nodes
- limited 2-hop relation expansion
- structured context packaging and grounded LLM answer generation
- simple FastAPI backend and mobile-friendly PWA prototype

This MVP is for **retrieval and basic reasoning validation**, not production causal accuracy.

## 2. Core Architecture

There is no separate graph database.

All data is stored in Weaviate collections:

```text
TextChunk
ImageChunk
RelationChunk
ConceptNode
```

Graph-like behavior is simulated in backend code:

- `TextChunk.concept_id` and `ImageChunk.concept_id` link evidence to nodes.
- `ConceptNode.concept_id` represents graph nodes.
- `RelationChunk.source_id` and `RelationChunk.target_id` represent graph edges.
- `RelationChunk` remains the source of truth for edges.

Vectors are generated outside Weaviate using local multilingual embeddings and stored as self-provided vectors.

Maximum traversal depth:

```text
2 hops
```

## 3. Current Completed Work

Done:

- Local Weaviate Docker Compose setup with REST `8080` and gRPC `50051`.
- HTML parsing, nested JSON, topic-level `TextChunk` creation.
- SVG/image extraction and heading attachment via `section_id`.
- Excel relation ingestion from `Data/CHP WRCF.xlsx`.
- `ConceptNode` generation from chunk concepts and relation endpoints.
- Local multilingual embeddings with `intfloat/multilingual-e5-small`.
- `TextChunk`, `ImageChunk`, and evidence-first `ConceptNode` vectors.
- Weaviate storage with zero insert failures.
- Vector smoke tests for English, Hindi, image, and node retrieval.
- Retrieval context packaging with reranking, dedupe, context bounds, and gated 2-hop relation expansion.
- Two-stage answer layer: context compression agent then final answer agent.
- FastAPI MVP backend with `/health`, `/chat`, and `/transcribe`.
- Independent static PWA frontend with text input, voice recording, answer display, references, and diagram descriptions.
- Offline extractive answer smoke tests.
- Five default CHP retrieval prompts and smoke artifacts.

Current verified counts:

```text
TextChunk: 196 inserted, 0 failed
ImageChunk: 34 inserted, 0 failed
RelationChunk: 748 inserted, 0 failed
ConceptNode: 938 inserted, 0 failed
```

Concept-node vector split:

```text
Evidence-backed ConceptNode vectors: 179
Relation-only ConceptNode vectors: 759
Total ConceptNode vectors: 938
```

Important files:

```text
src/core/
src/extraction/
src/graph/
src/embedding/
src/storage/
src/retrieval/
src/answering/
src/providers/
src/server/
src/cli/
src/eval/
src/api.py
src/run_ingestion.py
src/run_retrieval.py
src/run_answer.py
frontend/
```

The backend is now organized by lifecycle:

```text
one-time indexing: extraction -> graph -> embedding -> storage
per-query runtime: retrieval -> answering -> server/api
support: core config, providers, cli, eval
```

Generated artifacts:

```text
artifacts/ingestion/*.json
artifacts/ingestion/by_file/*.json
artifacts/retrieval/test_prompts.json
artifacts/retrieval/context_prompt_*.json
artifacts/retrieval/context_belt_drift.json
artifacts/retrieval/smoke_summary.json
artifacts/answers/*.json
```

## 4. Data Model

### TextChunk

Stores topic-level semantic text chunks from HTML. It has a self-provided vector from `content` when `--embed` is used.

### ImageChunk

Stores extracted diagram/image descriptions linked to headings. It has a self-provided vector from `description` when `--embed` is used.

### RelationChunk

Stores graph-like Excel edges with `source_id`, `target_id`, `relation_type`, `description`, and trace metadata. It is the source of truth for graph edges.

### ConceptNode

Represents graph-like nodes derived from chunk concepts and relation endpoints.

Important metadata:

```text
has_evidence
embedding_source
retrieval_weight
```

Embedding policy:

- nodes with linked text/image evidence use weighted averages of chunk vectors,
- text vector weight is `1.0`,
- image vector weight is `0.8`,
- relation-only nodes embed compact label/relation text,
- relation-only nodes use `retrieval_weight = 0.35` during retrieval reranking.

## 5. Phase Plan To MVP

## Phase A - Text + Structure Ingestion

Status:

```text
Done
```

## Phase B - Image / Diagram Extraction

Status:

```text
Done
```

## Phase C - Embeddings

Status:

```text
Done
```

Completed:

- text embeddings,
- image-description embeddings,
- evidence-first concept-node embeddings,
- relation-only concept-node embeddings,
- self-provided vectors stored in Weaviate.

## Phase D - Excel Relation Ingestion + Concept Nodes

Status:

```text
Done
```

## Phase E - Query Retrieval + 2-Hop Expansion

Status:

```text
Done
```

Current retrieval flow:

```text
User query
  -> embed query
  -> retrieve top-k TextChunk
  -> retrieve top-k ImageChunk
  -> retrieve top-k ConceptNode
  -> supplement text/image candidates with lexical evidence matches
  -> rerank evidence using operational relevance and generic-instruction penalties
  -> seed graph from retrieved concept IDs
  -> add high-confidence relation-only node seeds for graph expansion
  -> expand scored RelationChunk edges max 2 hops, bidirectionally
  -> fetch extra linked TextChunk/ImageChunk evidence
  -> dedupe and cap context_for_llm_later
  -> return structured context package
```

Retrieval package shape:

```text
query
seed_results
graph_expansion
expanded_evidence
context_for_llm_later
retrieval_diagnostics
```

Smoke test result:

```text
5 / 5 retrieval prompts passed
```

Default LLM-facing context bounds:

```text
text_blocks <= 8
image_blocks <= 3
relation_blocks <= 10
```

Some narrow course concepts, such as belt drift, may have no relation trace because the current Excel graph has low overlap with course heading concepts. Broad process prompts, such as coal flow and transfer point hazards, do return relation expansion.

## Phase F - Grounded Answer Generation

Status:

```text
Done, Groq live-call review pending
```

Current flow:

```text
retrieval context
  -> context compressor
  -> compact citation-preserving evidence
  -> final answer generator
  -> answer JSON with citations and coverage notes
```

Current behavior:

- Groq is the default LLM provider path via `GROQ_API_KEY`.
- Compressor model default: `llama-3.1-8b-instant`.
- Answer model default: `llama-3.3-70b-versatile`.
- Offline extractive fallback is available and verified.
- Answers preserve citations and disclose missing relation trace.

## Phase G - QA / Evaluation

Status:

```text
Partially started
```

Current QA:

- Python code compiles.
- Artifact generation verified.
- Validation report passes.
- Weaviate insert counts verified.
- Text/image/node vector retrieval verified.
- 5 retrieval context packages verified.
- Retrieval quality checks verified for belt drift, coal flow, and transfer-point prompts.
- 2-hop limit verified in smoke summary.
- 5 answer-layer smoke tests passed in offline/extractive mode.
- Compression is smaller than retrieval context and keeps citations.

Future QA:

- Set `GROQ_API_KEY` and review live Groq output for all 5 prompts.
- Add quality rubric checks for final Groq answers.

## Phase H - MVP API + PWA UI

Status:

```text
Implemented, local end-to-end verification pending
```

Current UI/API flow:

```text
Browser/PWA
  -> text question POST /chat
  -> retrieve_context()
  -> compress_context()
  -> generate_grounded_answer()
  -> simplified answer/references/images JSON

Browser/PWA
  -> record short audio
  -> POST /transcribe
  -> Groq whisper-large-v3-turbo
  -> transcript fills text box
```

Current behavior:

- Backend compatibility entrypoint is `src/api.py`; implementation lives in `src/server/app.py`.
- Frontend is independent static HTML/CSS/JS under `frontend/`.
- Voice input is record-then-transcribe, not streaming.
- No user accounts, database chat history, or auth are included.
- Cloud hosting is still pending.

## Phase I - Backend Source Restructure

Status:

```text
Done
```

Completed:

- Refactored flat `src/*.py` implementation into domain packages.
- Kept public commands stable through thin top-level wrappers.
- Kept `uvicorn src.api:app` stable.
- Moved one-time ingestion/indexing code away from per-query runtime code.
- Moved Groq provider, FastAPI server, CLI, and smoke tests into dedicated packages.

## 6. Current Commands

Start Weaviate:

```bash
cd infra/weaviate
docker compose up -d
```

Generate embedded artifacts and store cleanly in Weaviate:

```bash
python -m src.run_ingestion --store --embed --reset-text --reset-images --reset-relations --reset-concepts
```

Run vector smoke test:

```bash
python -m src.vector_smoke_test
```

Run retrieval smoke test:

```bash
python -m src.retrieval_smoke_test
```

Build one retrieval context package:

```bash
python -m src.run_retrieval --query "What are transfer point hazards?" --out artifacts/retrieval/context.json
```

Generate a grounded answer:

```bash
python -m src.run_answer --query "What are transfer point hazards?" --retrieval artifacts/retrieval/context.json --out artifacts/answers/answer.json
```

Run answer smoke test without Groq:

```bash
python -m src.answer_smoke_test
```

Run the MVP API:

```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

Serve the static frontend:

```bash
cd frontend
python -m http.server 5173
```

Open:

```text
http://localhost:5173
```

Useful retrieval tuning flags:

```bash
--max-context-text
--max-context-images
--max-context-relations
--disable-graph
--debug-full-context
```

## 7. Final MVP Definition

The MVP is complete when:

- Text chunks are ingested.
- Image chunks are extracted and attached to headings.
- Relation chunks are ingested from Excel.
- Concept nodes connect chunks and relations.
- Text, image, and node vectors are stored.
- Query retrieves text + image descriptions + concept nodes.
- Query expands relation context up to 2 hops.
- LLM generates grounded answers from retrieved context.
- Browser UI accepts text and voice questions.
- API returns answers, references, image descriptions, and coverage notes.
- System clearly exposes limitations when context is incomplete.

## 8. Next Immediate Task

Verify:

```text
Local FastAPI + PWA End-to-End Smoke Test
```

Why next:

- The API and frontend are implemented.
- Local verification still needs running Weaviate with embedded data.
- Voice transcription needs a browser microphone and live Groq key.
- After local smoke passes, the next work is Netlify/Railway deployment and Groq answer quality review.
