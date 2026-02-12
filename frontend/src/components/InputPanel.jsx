import { useState } from "react";

const LLM_OPTIONS = [
  { value: "groq", label: "Groq", desc: "Llama 3.3 70B — fast & free" },
  { value: "openai", label: "OpenAI", desc: "GPT-4o Mini" },
  { value: "anthropic", label: "Anthropic", desc: "Claude 3 Haiku" },
  { value: "ollama", label: "Ollama", desc: "Local — fully offline" },
];

const TTS_OPTIONS = [
  { value: "edge", label: "Edge TTS", desc: "Microsoft Neural — free" },
  { value: "groq", label: "Groq TTS", desc: "Orpheus — high quality" },
  { value: "coqui", label: "Coqui TTS", desc: "VITS — fully offline" },
];

export default function InputPanel({ onSubmit, isLoading }) {
  const [url, setUrl] = useState("");
  const [llm, setLlm] = useState("groq");
  const [tts, setTts] = useState("edge");
  const [genAudio, setGenAudio] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim() || isLoading) return;
    onSubmit({
      arxivUrl: url.trim(),
      llmBackend: llm,
      ttsEngine: tts,
      generateAudio: genAudio,
    });
  }

  const isValid = url.trim().length > 0;

  return (
    <form
      onSubmit={handleSubmit}
      className="glass p-6 sm:p-8 w-full max-w-2xl mx-auto animate-fade-in-up"
      style={{ animationDelay: "0.1s" }}
    >
      {/* URL input */}
      <label className="block mb-2 text-sm font-medium text-white/60">
        arXiv Paper URL or ID
      </label>
      <div className="relative">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-white/30">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
        </div>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="e.g. https://arxiv.org/abs/2301.07041 or 2301.07041"
          className="input-glass pl-12"
          disabled={isLoading}
        />
      </div>

      {/* Advanced settings toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="mt-5 flex items-center gap-2 text-sm text-white/40 hover:text-white/70 transition-colors"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`transition-transform ${showAdvanced ? "rotate-90" : ""}`}
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        Advanced Settings
      </button>

      {/* Advanced panel */}
      <div
        className={`overflow-hidden transition-all duration-300 ${
          showAdvanced ? "max-h-[400px] opacity-100 mt-4" : "max-h-0 opacity-0"
        }`}
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 p-4 glass-sm">
          {/* LLM backend */}
          <div>
            <label className="block mb-2 text-xs font-medium text-white/50 uppercase tracking-wider">
              LLM Backend
            </label>
            <select
              value={llm}
              onChange={(e) => setLlm(e.target.value)}
              className="select-glass w-full"
              disabled={isLoading}
            >
              {LLM_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label} — {o.desc}
                </option>
              ))}
            </select>
          </div>

          {/* TTS engine */}
          <div>
            <label className="block mb-2 text-xs font-medium text-white/50 uppercase tracking-wider">
              TTS Engine
            </label>
            <select
              value={tts}
              onChange={(e) => setTts(e.target.value)}
              className="select-glass w-full"
              disabled={isLoading}
            >
              {TTS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label} — {o.desc}
                </option>
              ))}
            </select>
          </div>

          {/* Generate audio toggle */}
          <div className="sm:col-span-2 flex items-center justify-between">
            <div>
              <p className="text-sm text-white/70 font-medium">Generate Audio</p>
              <p className="text-xs text-white/35 mt-0.5">
                Disable to get transcript only (faster)
              </p>
            </div>
            <button
              type="button"
              className={`toggle-track ${genAudio ? "active" : ""}`}
              onClick={() => setGenAudio(!genAudio)}
              disabled={isLoading}
            >
              <div className="toggle-knob" />
            </button>
          </div>
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!isValid || isLoading}
        className="btn-glow w-full mt-6 flex items-center justify-center gap-3 text-base"
      >
        {isLoading ? (
          <>
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="32" strokeDashoffset="12" strokeLinecap="round" />
            </svg>
            Generating…
          </>
        ) : (
          <>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Generate Podcast
          </>
        )}
      </button>
    </form>
  );
}
