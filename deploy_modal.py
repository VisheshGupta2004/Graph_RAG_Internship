import modal

app = modal.App("graphrag-backend")

image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
)

@app.function(image=image)
@modal.asgi_app()
def fastapi_app():
    from src.api import app
    return app