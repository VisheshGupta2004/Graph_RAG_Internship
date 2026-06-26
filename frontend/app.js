const API_BASE_URL = "https://graphraginternship-production.up.railway.app";
// const API_BASE_URL = "http://localhost:8000";

const questionInput = document.getElementById("questionInput");
const sendButton = document.getElementById("sendButton");
const micButton = document.getElementById("micButton");
const micButtonText = document.getElementById("micButtonText");
const voiceHint = document.getElementById("voiceHint");
const apiStatus = document.getElementById("apiStatus");
const statePanel = document.getElementById("statePanel");
const answerPanel = document.getElementById("answerPanel");
const answerText = document.getElementById("answerText");
const referencesGrid = document.getElementById("referencesGrid");
const referencesList = document.getElementById("referencesList");
const imagesList = document.getElementById("imagesList");
const notesPanel = document.getElementById("notesPanel");
const coverageNotes = document.getElementById("coverageNotes");

let mediaRecorder = null;
let recordedChunks = [];

sendButton.addEventListener("click", submitQuestion);
micButton.addEventListener("click", toggleRecording);
questionInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    submitQuestion();
  }
});

window.addEventListener("load", () => {
  registerServiceWorker();
  checkHealth();
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    micButton.disabled = true;
    voiceHint.textContent = "Voice recording is not supported in this browser.";
  }
});

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error("Health check failed");
    const data = await response.json();
    apiStatus.textContent = data.groq_api_key_present ? "Ready" : "No Groq key";
    apiStatus.className = data.groq_api_key_present ? "status-pill ok" : "status-pill error";
  } catch (error) {
    apiStatus.textContent = "Offline";
    apiStatus.className = "status-pill error";
  }
}

async function submitQuestion() {
  const message = questionInput.value.trim();
  if (!message) {
    showState("Type or record a question first.", true);
    return;
  }

  setBusy(true, "Finding grounded answer...");
  clearResults();

  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.detail || "Chat request failed");

    renderAnswer(data);
    hideState();
  } catch (error) {
    showState(error.message || "Unable to get an answer.", true);
  } finally {
    setBusy(false);
  }
}

async function toggleRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    const mimeType = preferredMimeType();
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) recordedChunks.push(event.data);
    });

    mediaRecorder.addEventListener("stop", async () => {
      stream.getTracks().forEach((track) => track.stop());
      micButton.classList.remove("recording");
      micButtonText.textContent = "Record";
      await transcribeRecording(mimeType || "audio/webm");
    });

    mediaRecorder.start();
    micButton.classList.add("recording");
    micButtonText.textContent = "Stop";
    showState("Recording... tap Stop when finished.", false);
  } catch (error) {
    showState("Microphone access was blocked or unavailable.", true);
  }
}

async function transcribeRecording(mimeType) {
  if (!recordedChunks.length) {
    showState("No audio was recorded.", true);
    return;
  }

  setBusy(true, "Transcribing audio...");
  try {
    const extension = mimeType.includes("wav") ? "wav" : "webm";
    const blob = new Blob(recordedChunks, { type: mimeType });
    const formData = new FormData();
    formData.append("file", blob, `question.${extension}`);

    const response = await fetch(`${API_BASE_URL}/transcribe`, {
      method: "POST",
      body: formData,
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.detail || "Transcription failed");

    questionInput.value = data.text || "";
    hideState();
    questionInput.focus();
  } catch (error) {
    showState(error.message || "Unable to transcribe audio.", true);
  } finally {
    setBusy(false);
  }
}

function preferredMimeType() {
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/wav"];
  return types.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function renderAnswer(data) {
  answerText.textContent = data.answer || "No answer returned.";
  answerPanel.hidden = false;

  renderReferences(data.references || []);
  renderImages(data.images || []);
  referencesGrid.hidden = !(data.references?.length || data.images?.length);

  renderCoverage(data.coverage_notes || {});
}

function renderReferences(items) {
  referencesList.innerHTML = "";
  if (!items.length) {
    referencesList.appendChild(emptyItem("No references returned."));
    return;
  }
  items.forEach((item) => {
    referencesList.appendChild(
      card(
        item.title || item.id || "Reference",
        [item.source_file, item.concept_id].filter(Boolean).join(" | "),
        item.id || "",
      ),
    );
  });
}

function renderImages(items) {
  imagesList.innerHTML = "";
  if (!items.length) {
    imagesList.appendChild(emptyItem("No diagram descriptions returned."));
    return;
  }
  items.forEach((item) => {
    imagesList.appendChild(imageCard(item));
  });
}

function renderCoverage(notes) {
  const weaknesses = notes.weaknesses || [];
  coverageNotes.innerHTML = "";
  if (!weaknesses.length) {
    coverageNotes.textContent = "Text, image, and relation coverage are shown when available.";
  } else {
    const list = document.createElement("ul");
    list.className = "notes-list";
    weaknesses.forEach((weakness) => {
      const item = document.createElement("li");
      item.textContent = weakness;
      list.appendChild(item);
    });
    coverageNotes.appendChild(list);
  }
  notesPanel.hidden = false;
}

function card(title, meta, body) {
  const element = document.createElement("article");
  element.className = "item";

  const titleElement = document.createElement("div");
  titleElement.className = "item-title";
  titleElement.textContent = title;
  element.appendChild(titleElement);

  if (meta) {
    const metaElement = document.createElement("div");
    metaElement.className = "item-meta";
    metaElement.textContent = meta;
    element.appendChild(metaElement);
  }

  if (body) {
    const bodyElement = document.createElement("div");
    bodyElement.className = "item-body";
    bodyElement.textContent = body;
    element.appendChild(bodyElement);
  }

  return element;
}

function imageCard(item) {
  const element = card(
    item.title || "Diagram",
    [item.source_file, item.concept_id].filter(Boolean).join(" | "),
    item.description || "",
  );

  if (item.asset_url) {
    const absoluteUrl = `${API_BASE_URL}${item.asset_url}`;
    const frame = document.createElement("div");
    frame.className = "diagram-frame";

    const image = document.createElement("img");
    image.alt = item.title || "Retrieved diagram";
    image.loading = "lazy";
    image.src = absoluteUrl;
    image.addEventListener("error", () => {
      frame.classList.add("diagram-frame-error");
      frame.textContent = "Diagram preview could not load.";
    });
    frame.appendChild(image);
    element.insertBefore(frame, element.firstChild);

    const link = document.createElement("a");
    link.className = "diagram-link";
    link.href = absoluteUrl;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "Open diagram";
    element.appendChild(link);
  }

  return element;
}

function emptyItem(text) {
  return card(text, "", "");
}

async function readJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
}

function setBusy(isBusy, message = "") {
  sendButton.disabled = isBusy;
  micButton.disabled = isBusy || !navigator.mediaDevices || !window.MediaRecorder;
  if (isBusy && message) showState(message, false);
}

function showState(message, isError) {
  statePanel.textContent = message;
  statePanel.className = isError ? "state-panel error" : "state-panel";
  statePanel.hidden = false;
}

function hideState() {
  statePanel.hidden = true;
}

function clearResults() {
  answerPanel.hidden = true;
  referencesGrid.hidden = true;
  notesPanel.hidden = true;
  answerText.textContent = "";
  referencesList.innerHTML = "";
  imagesList.innerHTML = "";
  coverageNotes.innerHTML = "";
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js").catch(() => {});
  }
}
