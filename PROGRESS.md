# Weaviate Graph RAG MVP - Progress

## Current Status

The project now covers **ingestion, local multilingual embeddings, concept-node vectors, tuned retrieval, context compression, grounded answer generation plumbing, a FastAPI API, and an independent mobile-friendly PWA prototype** for the Weaviate-only Graph RAG MVP. Groq is the default LLM provider path, with an offline extractive fallback for local verification.

The backend source is now structured into domain packages instead of a flat `src` folder.

Current generated artifact counts:

| Object type               | Count |
| ------------------------- | ----: |
| `TextChunk` objects     |   196 |
| `ImageChunk` objects    |    34 |
| `RelationChunk` objects |   748 |
| `ConceptNode` objects   |   938 |

Validation report:

```text
artifacts/ingestion/validation_report.json
passed = true
```

## Completed

- Local Weaviate Docker Compose setup.
- HTML parsing from `Data/`.
- Hierarchical nested JSON from HTML headings.
- iCard JavaScript-template extraction.
- Semantic text chunking at topic/concept level.
- SVG diagram extraction.
- Image/SVG attachment to nearest heading using `section_id`.
- Deterministic `concept_id` alignment for text and image chunks.
- Excel relation ingestion from `Data/CHP WRCF.xlsx`.
- `RelationChunk` edge generation.
- `ConceptNode` generation from chunk concepts and relation endpoints.
- Optional local embeddings for `TextChunk.content`, `ImageChunk.description`, and evidence-first `ConceptNode` vectors.
- Retrieval context packaging over text, images, nodes, and 2-hop relation expansion.
- Retrieval quality tuning: lexical supplement, evidence-aware reranking, generic instruction penalties, graph relation gating, dedupe, and bounded `context_for_llm_later`.
- Two-stage answer layer: context compression first, grounded final answer second.
- Groq Chat Completions wrapper using `GROQ_API_KEY`, plus offline extractive fallback.
- Groq speech-to-text helper using `whisper-large-v3-turbo`.
- FastAPI backend with `/health`, `/chat`, and `/transcribe`.
- Static PWA frontend with text input, record-then-transcribe voice input, answer rendering, references, diagram descriptions, and coverage notes.
- Frontend-specific guide in `frontend/UNDERSTAND_FRONTEND.md`.
- Backend package restructure into `core`, `extraction`, `graph`, `embedding`, `storage`, `retrieval`, `answering`, `providers`, `server`, `cli`, and `eval`.
- Thin top-level wrappers preserve existing commands and `uvicorn src.api:app`.
- Aggregate JSON artifacts.
- Per-file unified JSON artifacts.
- Validation report generation.
- Weaviate storage functions for text, image, relation, and concept-node objects.

## Processed Sources

HTML files:

- `Belt_Conveyor_L1_Course_COMPLETE.html`
- `Belt_Conveyor_L1_Course_HINDI.html`
- `track_hopper_feeder_L2_course.html`
- `Track_Hopper_iCard_Microlearning.html`

Excel file:

- `CHP WRCF.xlsx`

## Per-File Counts

| Source file                               | Text chunks | Image chunks |
| ----------------------------------------- | ----------: | -----------: |
| `Belt_Conveyor_L1_Course_COMPLETE.html` |          58 |           11 |
| `Belt_Conveyor_L1_Course_HINDI.html`    |          70 |           13 |
| `track_hopper_feeder_L2_course.html`    |          14 |            3 |
| `Track_Hopper_iCard_Microlearning.html` |          54 |            7 |

## Weaviate Collections

### `TextChunk`

Stores semantic text chunks from HTML.

Important fields:

- `chunk_id`
- `content`
- `title`
- `parent_title`
- `concept_id`
- `section_id`
- `source_file`
- `type`
- `metadata`

### `ImageChunk`

Stores diagram/image descriptions extracted from SVG or image blocks.

Important fields:

- `image_id`
- `description`
- `title`
- `parent_title`
- `concept_id`
- `section_id`
- `source_file`
- `type`
- `metadata`

### `RelationChunk`

Stores graph-like edges generated from Excel.

Important fields:

- `relation_id`
- `source_id`
- `target_id`
- `relation_type`
- `description`
- `metadata`

`RelationChunk` is the source of truth for graph edges.

### `ConceptNode`

Stores graph-like nodes derived from shared IDs.

Important fields:

- `concept_id`
- `label`
- `node_type`
- `text_chunk_ids`
- `image_ids`
- `source_relation_ids`
- `target_relation_ids`
- `metadata`
- vector

`ConceptNode` links chunks and relation edges by ID and stores a self-provided vector when `--embed` is used. Evidence-backed nodes inherit weighted text/image vectors; relation-only nodes use compact label/relation text and a lower retrieval weight. It does not replace `RelationChunk`.

## Generated Artifacts

Aggregate artifacts:

```text
artifacts/ingestion/nested_structure.json
artifacts/ingestion/semantic_chunks.json
artifacts/ingestion/image_chunks.json
artifacts/ingestion/relation_chunks.json
artifacts/ingestion/textchunk_objects.json
artifacts/ingestion/imagechunk_objects.json
artifacts/ingestion/relationchunk_objects.json
artifacts/ingestion/conceptnode_objects.json
artifacts/ingestion/validation_report.json
```

Per-file artifacts:

```text
artifacts/ingestion/by_file/*.json
```

Each per-file JSON now contains:

```json
{
  "source_file": "",
  "nested_json": {},
  "text_chunks": [],
  "image_chunks": [],
  "relations": [],
  "textchunk_objects": [],
  "imagechunk_objects": [],
  "relationchunk_objects": [],
  "conceptnode_objects": []
}
```

When `--embed` is used, `textchunk_objects.json` and `imagechunk_objects.json` include `_vector` values for Weaviate self-provided vectors.
`conceptnode_objects.json` also includes `_vector` values and metadata fields for `has_evidence`, `embedding_source`, and `retrieval_weight`.

Retrieval artifacts:

```text
artifacts/retrieval/test_prompts.json
artifacts/retrieval/context_prompt_*.json
artifacts/retrieval/context_belt_drift.json
artifacts/retrieval/smoke_summary.json
```

Answer artifacts:

```text
artifacts/answers/compressed_*.json
artifacts/answers/answer_*.json
artifacts/answers/answer_smoke_summary.json
```

Frontend files:

```text
frontend/index.html
frontend/styles.css
frontend/app.js
frontend/manifest.json
frontend/service-worker.js
frontend/icons/app-icon.svg
frontend/UNDERSTAND_FRONTEND.md
```

Backend package layout:

```text
src/core
src/extraction
src/graph
src/embedding
src/storage
src/retrieval
src/answering
src/providers
src/server
src/cli
src/eval
```

## Relation Ingestion

Relations are generated from workbook hierarchy:

- `FG -> PWO` as `has_pwo`
- `PWO -> SWO` as `has_swo`
- `SWO -> Skill` as `has_skill`
- `Skill -> Task` as `has_task`
- `Task -> Control Point` as `has_control_point`
- dependency values as `depends_on`

Each relation keeps Excel traceability:

- workbook file
- sheet name
- row number
- source label
- target label
- evidence text

## Main Commands

Generate artifacts only:

```bash
python -m src.run_ingestion
```

Store everything into Weaviate after resetting collections:

```bash
python -m src.run_ingestion --store --reset-text --reset-images --reset-relations --reset-concepts
```

Generate local multilingual embeddings and store everything into Weaviate:

```bash
python -m src.run_ingestion --store --embed --reset-text --reset-images --reset-relations --reset-concepts
```

Run vector retrieval smoke tests after embedded storage:

```bash
python -m src.vector_smoke_test
```

Run the full retrieval smoke test for the 5 default prompts:

```bash
python -m src.retrieval_smoke_test
```

Build one retrieval context package:

```bash
python -m src.run_retrieval --query "Why is belt drift dangerous?" --out artifacts/retrieval/context.json
```

Compress context and generate a grounded answer:

```bash
python -m src.run_answer --query "Why is belt drift dangerous?" --retrieval artifacts/retrieval/context.json --out artifacts/answers/answer.json
```

Run answer-layer smoke tests without Groq:

```bash
python -m src.answer_smoke_test
```

Run the FastAPI backend:

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
--max-context-text 8
--max-context-images 3
--max-context-relations 10
--disable-graph
--debug-full-context
```

Start local Weaviate:

```bash
cd infra/weaviate
docker compose up -d
```

## Current Verification

Verified successfully:

- Python code compiles.
- Artifact generation works.
- Text count remains `196`.
- Image count remains `34`.
- Relation count is `748`.
- Concept node count is `938`.
- Local embedding generation works with `intfloat/multilingual-e5-small`.
- Concept node vector generation works for all `938` nodes.
- Validation report passes.
- Relation spot checks include conveyor and track-hopper relations.
- Weaviate embedded storage completed with zero insert failures.
- Vector smoke test passed for English, Hindi, and image/diagram queries.
- Vector smoke test includes ConceptNode retrieval.
- Retrieval smoke test passed for all 5 default prompts.
- Retrieval smoke test now checks context caps and selected quality expectations.
- Belt drift retrieval ranks belt-drift evidence above generic course/readiness chunks.
- 2-hop graph expansion is enforced.
- Retrieved smoke-test objects all resolved to matching `ConceptNode` records.
- Offline answer smoke test passed for all 5 prompts.
- Compressed contexts are smaller than retrieval contexts and preserve citations.
- API/frontend files were added for local prototype testing.
- `python -m compileall src` passed after API changes.
- `src.api` imports successfully.
- FastAPI lightweight checks passed: `/health` returns `200`, empty `/chat` returns `400`, missing `/transcribe` file returns validation `422`.
- Added `/images/{image_id}.svg` so frontend diagram cards can render original inline SVG diagrams, not only text descriptions.
- Backend package restructure compile/import checks passed.
- `python -m src.run_ingestion` passed with 196 text chunks, 34 image chunks, 748 relations, and 938 concept nodes.
- `python -m src.answer_smoke_test` passed all 5 prompts.
- `python -m src.retrieval_smoke_test` passed all 5 prompts.
- `python -m src.vector_smoke_test` passed text, Hindi, image, and concept-node checks.
- `python -m src.run_retrieval` worked for the coal-flow diagram prompt.
- `python -m src.run_answer --offline` worked for the transfer-point prompt.

Verified Weaviate counts:

- `TextChunk`: 196 inserted, 0 failed
- `ImageChunk`: 34 inserted, 0 failed
- `RelationChunk`: 748 inserted, 0 failed
- `ConceptNode`: 938 inserted, 0 failed

## Remaining Work

- Install new API dependencies from `requirements.txt` if the environment does not already have them.
- Run local FastAPI `/health`, `/chat`, and `/transcribe` checks.
- Test the frontend in a browser at `http://localhost:5173`.
- Verify real Groq answer and speech-to-text calls with `GROQ_API_KEY`.
- Improve answer wording after reviewing Groq outputs on the 5 prompt set.
- Decide cloud Weaviate hosting and deploy frontend/backend to Netlify/Railway or equivalent.
