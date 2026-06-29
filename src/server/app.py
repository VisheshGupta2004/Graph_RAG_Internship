from __future__ import annotations

from time import perf_counter
from typing import Any

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..answering.compression import compress_context
from ..answering.generator import generate_grounded_answer
from ..core.config import (
    API_CORS_ORIGINS,
    DATA_DIR,
    GROQ_ANSWER_MODEL,
    GROQ_COMPRESSOR_MODEL,
    GROQ_TRANSCRIPTION_MODEL,
    WEAVIATE_GRPC_HOST,
    WEAVIATE_GRPC_PORT,
    WEAVIATE_GRPC_SECURE,
    WEAVIATE_HOST,
    WEAVIATE_HTTP_SECURE,
    WEAVIATE_PORT,
)
from ..embedding.service import warm_embedding_model
from ..extraction.image_extraction import find_svg_by_image_id
from ..providers.groq_provider import LLMProviderError, groq_transcribe_audio, has_groq_api_key
from ..retrieval import retrieve_context


app = FastAPI(
    title="CHP Graph RAG MVP API",
    version="0.1.0",
    description="Minimal API for the CHP Graph RAG text and voice prototype.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def warm_models() -> None:
    warm_embedding_model()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question to answer from CHP training evidence.")


class ChatResponse(BaseModel):
    query: str
    answer: str
    references: list[dict[str, Any]]
    images: list[dict[str, Any]]
    coverage_notes: dict[str, Any]
    metadata: dict[str, Any]


class TranscriptionResponse(BaseModel):
    text: str


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "groq_api_key_present": has_groq_api_key(),
        "weaviate": {
            "host": WEAVIATE_HOST,
            "port": WEAVIATE_PORT,
            "http_secure": WEAVIATE_HTTP_SECURE,
            "grpc_host": WEAVIATE_GRPC_HOST,
            "grpc_port": WEAVIATE_GRPC_PORT,
            "grpc_secure": WEAVIATE_GRPC_SECURE,
        },
        "models": {
            "compressor": GROQ_COMPRESSOR_MODEL,
            "answer": GROQ_ANSWER_MODEL,
            "transcription": GROQ_TRANSCRIPTION_MODEL,
        },
        "cors_origins": API_CORS_ORIGINS,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        payload = await run_in_threadpool(_answer_question, message)
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"RAG pipeline failed: {exc}") from exc

    return ChatResponse(**payload)


@app.get("/images/{image_id}.svg")
async def image_svg(image_id: str) -> Response:
    if not image_id.strip():
        raise HTTPException(status_code=400, detail="Image id cannot be empty.")

    try:
        svg = await run_in_threadpool(_find_svg_asset, image_id.strip())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Image lookup failed: {exc}") from exc

    if not svg:
        raise HTTPException(status_code=404, detail="SVG image not found.")
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(file: UploadFile = File(...), language: str | None = None) -> TranscriptionResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Audio filename is required.")

    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Audio file cannot be empty.")

    try:
        text = await run_in_threadpool(
            groq_transcribe_audio,
            file.filename,
            audio,
            file.content_type,
            GROQ_TRANSCRIPTION_MODEL,
            language,
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc

    return TranscriptionResponse(text=text)


def _answer_question(message: str) -> dict[str, Any]:
    total_start = perf_counter()
    step_start = total_start

    retrieval_context = retrieve_context(message)
    timings = {
        "retrieval_seconds": _elapsed_seconds(step_start),
    }

    step_start = perf_counter()
    compressed_context = compress_context(retrieval_context, use_llm=False, allow_fallback=True)
    timings["compression_seconds"] = _elapsed_seconds(step_start)

    step_start = perf_counter()
    answer_payload = generate_grounded_answer(compressed_context, use_llm=True, allow_fallback=True)
    timings["answer_generation_seconds"] = _elapsed_seconds(step_start)

    step_start = perf_counter()
    ui = answer_payload.get("ui_response", {})
    metadata = dict(answer_payload.get("answer_metadata", {}))
    metadata["compression_mode"] = compressed_context.get("compression_metadata", {}).get("mode")
    metadata["retrieval_counts"] = retrieval_context.get("retrieval_diagnostics", {}).get("final_context_counts", {})
    metadata["retrieval_timings"] = retrieval_context.get("retrieval_diagnostics", {}).get("timings", {})
    metadata["has_relation_trace"] = answer_payload.get("coverage_notes", {}).get("has_relation_trace")
    timings["response_packaging_seconds"] = _elapsed_seconds(step_start)
    timings["total_seconds"] = _elapsed_seconds(total_start)
    metadata["timings"] = timings
    print(
        "[chat timings] "
        f"retrieval={timings['retrieval_seconds']}s "
        f"compression={timings['compression_seconds']}s "
        f"answer={timings['answer_generation_seconds']}s "
        f"packaging={timings['response_packaging_seconds']}s "
        f"total={timings['total_seconds']}s",
        flush=True,
    )
    _print_retrieval_timings(metadata["retrieval_timings"])

    return {
        "query": answer_payload.get("query") or message,
        "answer": ui.get("answer_text") or answer_payload.get("answer", ""),
        "references": ui.get("citations") or answer_payload.get("citations", []),
        "images": _with_image_asset_urls(ui.get("retrieved_images") or answer_payload.get("retrieved_images", [])),
        "coverage_notes": ui.get("coverage_notes") or answer_payload.get("coverage_notes", {}),
        "metadata": metadata,
    }


def _elapsed_seconds(start: float) -> float:
    return round(perf_counter() - start, 3)


def _print_retrieval_timings(timings: dict[str, Any]) -> None:
    if not timings:
        return
    ordered_keys = [
        "weaviate_setup_seconds",
        "query_embedding_seconds",
        "query_terms_seconds",
        "text_vector_search_seconds",
        "image_vector_search_seconds",
        "node_vector_search_seconds",
        "node_rerank_seconds",
        "fetch_all_text_seconds",
        "fetch_all_images_seconds",
        "fetch_all_nodes_seconds",
        "fetch_all_relations_seconds",
        "text_lexical_merge_rerank_seconds",
        "image_lexical_merge_rerank_seconds",
        "seed_build_seconds",
        "graph_expansion_seconds",
        "expanded_evidence_seconds",
        "context_build_seconds",
        "total_retrieval_seconds",
    ]
    parts = [f"{key}={timings[key]}s" for key in ordered_keys if key in timings]
    print("[retrieval timings] " + " ".join(parts), flush=True)


def _with_image_asset_urls(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for image in images:
        item = dict(image)
        image_id = item.get("image_id") or item.get("id")
        if image_id:
            item["asset_url"] = f"/images/{image_id}.svg"
        enriched.append(item)
    return enriched


def _find_svg_asset(image_id: str) -> str | None:
    for html_path in sorted(DATA_DIR.glob("*.html")):
        svg = find_svg_by_image_id(html_path, image_id)
        if svg:
            return svg
    return None
