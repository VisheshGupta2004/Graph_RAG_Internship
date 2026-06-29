import modal

app = modal.App("graphrag-backend")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("build-essential", "git")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("src", remote_path="/root/src")
    .add_local_dir("Data", remote_path="/root/Data")
)

WEAVIATE_HTTP_HOST = "enchanting-learning-production-9a55.up.railway.app"
WEAVIATE_GRPC_HOST = "reseau.proxy.rlwy.net"

backend_env = {
    "WEAVIATE_HOST": WEAVIATE_HTTP_HOST,
    "WEAVIATE_PORT": "443",
    "WEAVIATE_HTTP_SECURE": "true",

    "WEAVIATE_GRPC_HOST": WEAVIATE_GRPC_HOST,
    "WEAVIATE_GRPC_PORT": "17337",
    "WEAVIATE_GRPC_SECURE": "false",

    "API_CORS_ORIGINS": "https://chpgraphrag.netlify.app",
    "GROQ_COMPRESSOR_MODEL": "llama-3.1-8b-instant",
    "GROQ_ANSWER_MODEL": "openai/gpt-oss-20b",
    "GROQ_TRANSCRIPTION_MODEL": "whisper-large-v3-turbo",
}

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("graphrag-secrets")],
    env=backend_env,
    timeout=600,
    memory=4096,
)
@modal.asgi_app()
def fastapi_app():
    from src.api import app as api_app

    return api_app
