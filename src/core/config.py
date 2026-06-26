import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "Data"
EXCEL_PATH = DATA_DIR / "CHP WRCF.xlsx"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "ingestion"
RETRIEVAL_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "retrieval"
ANSWER_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "answers"

TEXT_COLLECTION = "TextChunk"
IMAGE_COLLECTION = "ImageChunk"
RELATION_COLLECTION = "RelationChunk"
CONCEPT_COLLECTION = "ConceptNode"

EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_BATCH_SIZE = 32

GROQ_COMPRESSOR_MODEL = os.getenv("GROQ_COMPRESSOR_MODEL", "llama-3.1-8b-instant")
GROQ_ANSWER_MODEL = os.getenv("GROQ_ANSWER_MODEL", "openai/gpt-oss-20b")
GROQ_ANSWER_MAX_TOKENS = int(os.getenv("GROQ_ANSWER_MAX_TOKENS", "1000"))
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "localhost")
WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", "8080"))
WEAVIATE_GRPC_PORT = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

API_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "API_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
GROQ_TRANSCRIPTION_MODEL = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
