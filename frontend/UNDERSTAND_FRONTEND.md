# Understand The Frontend Prototype

This frontend is an independent static PWA for the CHP Graph RAG MVP.

It is intentionally framework-free so it can be hosted on Netlify or any static file host.

## Files

```text
frontend/index.html
frontend/styles.css
frontend/app.js
frontend/manifest.json
frontend/service-worker.js
frontend/icons/app-icon.svg
```

## Local Run

Start the FastAPI backend first:

```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

Serve the frontend:

```bash
cd frontend
python -m http.server 5173
```

Open:

```text
http://localhost:5173
```

## API Base URL

`frontend/app.js` has one constant:

```js
const API_BASE_URL = "http://localhost:8000";
```

For Netlify deployment, change this to the deployed backend URL or replace it during build/deploy.

## UI Flow

Text path:

```text
User enters question
  -> POST /chat
  -> render answer, references, image descriptions, coverage notes
  -> render diagram images from GET /images/{image_id}.svg when asset_url is present
```

Voice path:

```text
User taps Record
  -> browser MediaRecorder captures audio
  -> user taps Stop
  -> POST /transcribe
  -> transcript fills the textarea
  -> user edits or submits to /chat
```

## PWA Behavior

The manifest and service worker make the static shell installable and cache basic frontend files.

The RAG answer flow is not available offline because it requires the backend, Weaviate, embeddings, and Groq.

## Browser Notes

- Microphone recording requires HTTPS on deployed hosts.
- Localhost is allowed by modern browsers for development.
- Unsupported browsers disable the voice button and keep text chat usable.
