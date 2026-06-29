# GraphRAG Internship

A Graph Retrieval-Augmented Generation (GraphRAG) system for **Industrial Function training material** that combines semantic search, knowledge graph expansion, and grounded answer generation. The system retrieves evidence from structured documents, diagrams, and graph relationships before generating responses, ensuring every answer is supported by relevant source material.

---

# Features

* Graph Retrieval-Augmented Generation (GraphRAG)
* Semantic search over text and diagrams
* Knowledge graph construction and traversal
* Grounded answer generation with citations
* Multilingual embedding support (English + Hindi)
* Voice transcription using Groq Whisper
* Progressive Web App (PWA)
* FastAPI backend
* Weaviate vector database
* Modular and extensible architecture

---

# System Architecture

```text
                     +----------------------+
                     |     Frontend (PWA)   |
                     |   Netlify Deployment |
                     +----------+-----------+
                                |
                                |
                                ▼
                    +------------------------+
                    |    FastAPI Backend     |
                    |       (Modal)          |
                    +-----+------------+-----+
                          |            |
                          |            |
              +-----------+            +----------------+
              |                                 |
              ▼                                 ▼
      +---------------+                 +---------------+
      |   Weaviate    |                 |    Groq API   |
      |   (Railway)   |                 | LLM + Whisper |
      +---------------+                 +---------------+
```

---

# Retrieval Pipeline

```text
User Query
      │
      ▼
Generate Query Embedding
      │
      ▼
Vector Search
(TextChunk / ImageChunk / ConceptNode)
      │
      ▼
Lexical Merge & Re-ranking
      │
      ▼
Knowledge Graph Expansion
      │
      ▼
Evidence Collection
      │
      ▼
Context Compression
      │
      ▼
Grounded Answer Generation
      │
      ▼
Response + Citations + Images
```

---

# Technology Stack

| Component       | Technology                         |
| --------------- | ---------------------------------- |
| Backend         | FastAPI                            |
| Frontend        | HTML, CSS, JavaScript (PWA)        |
| Vector Database | Weaviate                           |
| Embedding Model | intfloat/multilingual-e5-small     |
| LLM             | Groq                               |
| Speech-to-Text  | Groq Whisper                       |
| Knowledge Graph | Custom ConceptNode + RelationChunk |
| Deployment      | Modal + Railway + Netlify          |

---

# Project Structure

```text
Graph_RAG_Internship/

├── Data/                   # Source HTML files & workbook
├── artifacts/              # Generated ingestion/retrieval artifacts
├── frontend/               # Progressive Web App
├── infra/
│   └── weaviate/           # Docker compose for Weaviate
│
├── src/
│   ├── answering/
│   ├── cli/
│   ├── core/
│   ├── embedding/
│   ├── eval/
│   ├── extraction/
│   ├── graph/
│   ├── providers/
│   ├── retrieval/
│   ├── server/
│   ├── storage/
│   ├── api.py
│   └── run_ingestion.py
│
├── requirements.txt
├── Dockerfile
├── Procfile
├── .env.example
└── README.md
```

---

# Data Pipeline

### Offline Ingestion

* Parse HTML training modules
* Extract semantic text chunks
* Extract image descriptions
* Parse CHP workbook relationships
* Build Concept Nodes
* Generate multilingual embeddings
* Store everything in Weaviate

---

### Online Query Pipeline

* Generate query embedding
* Retrieve relevant text, images, and concepts
* Expand through the knowledge graph
* Assemble contextual evidence
* Compress context
* Generate grounded response using Groq
* Return answer, citations, and diagrams

---

# Data Objects

## TextChunk

Stores semantic sections extracted from training material.

## ImageChunk

Stores textual descriptions of diagrams to enable semantic retrieval.

## RelationChunk

Represents graph edges extracted from the CHP workbook.

## ConceptNode

Connects text evidence, image evidence, and graph relations into a unified knowledge graph.

---

# API Endpoints

## Health Check

```
GET /health
```

Returns service status and configuration.

---

## Chat

```
POST /chat
```

Returns grounded answers with supporting evidence.

---

## Speech-to-Text

```
POST /transcribe
```

Converts user audio into text using Groq Whisper.

---

## Diagram Retrieval

```
GET /images/{image_id}.svg
```

Returns SVG diagrams referenced in responses.

---

# Local Development

## 1. Clone Repository

```bash
git clone https://github.com/VisheshGupta2004/Graph_RAG_Internship
cd Graph_RAG_Internship
```

---

## 2. Create Virtual Environment

```bash
python -m venv .venv
```

Activate:

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment

Copy

```text
.env.example
```

to

```text
.env
```

and update:

```
GROQ_API_KEY=
WEAVIATE_HOST=
WEAVIATE_PORT=
WEAVIATE_GRPC_PORT=
```

---

## 5. Start Weaviate

```bash
cd infra/weaviate
docker compose up -d
```

---

## 6. Populate the Knowledge Base

```bash
python -m src.run_ingestion \
    --store \
    --embed \
    --reset-text \
    --reset-images \
    --reset-relations \
    --reset-concepts
```

---

## 7. Start Backend

```bash
uvicorn src.api:app --reload
```

---

## 8. Start Frontend

```bash
cd frontend
python -m http.server 5173
```

Open

```
http://localhost:5173
```

---

# Deployment

## Frontend

* Netlify

## Backend

* Modal

## Vector Database

* Railway (Weaviate)

## LLM

* Groq

---

# Future Improvements

* Hybrid BM25 + Vector Retrieval
* Relation Embeddings
* Better Concept Normalization
* Learned Re-ranking
* Multimodal Embeddings
* Agentic Retrieval
* LLM Context Compression
* Production Authentication
* CI/CD Pipeline
* Monitoring & Observability

---

# Project Status

| Component                  | Status |
| -------------------------- | ------ |
| HTML Parsing               | ✅     |
| Semantic Chunking          | ✅     |
| Image Extraction           | ✅     |
| Knowledge Graph            | ✅     |
| Concept Nodes              | ✅     |
| Local Embeddings           | ✅     |
| Weaviate Storage           | ✅     |
| Retrieval Pipeline         | ✅     |
| Graph Expansion            | ✅     |
| Context Compression        | ✅     |
| Grounded Answer Generation | ✅     |
| FastAPI Backend            | ✅     |
| Voice Transcription        | ✅     |
| Frontend PWA               | ✅     |
| Docker Support             | 🚧     |
| CI/CD                      | 🚧     |
| Production Deployment      | 🚧     |

---

# License

This project was developed as part of a GraphRAG internship focused on improving industrial training systems using Retrieval-Augmented Generation and Knowledge Graphs.
