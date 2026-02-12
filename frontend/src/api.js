const API_BASE = "http://localhost:8000";

export async function startGeneration({ arxivUrl, llmBackend, ttsEngine, generateAudio }) {
  const res = await fetch(`${API_BASE}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      arxiv_url: arxivUrl,
      llm_backend: llmBackend,
      tts_engine: ttsEngine,
      generate_audio: generateAudio,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json();
}

export function streamJobProgress(jobId, onUpdate) {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`${API_BASE}/api/stream/${jobId}`);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onUpdate(data);
        if (data.status === "done" || data.status === "error") {
          source.close();
          resolve(data);
        }
      } catch (e) {
        console.error("SSE parse error:", e);
      }
    };

    source.onerror = () => {
      source.close();
      reject(new Error("Lost connection to server"));
    };
  });
}

export async function fetchJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/api/status/${jobId}`);
  if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
  return res.json();
}

export function getAudioUrl(path) {
  return `${API_BASE}${path}`;
}
