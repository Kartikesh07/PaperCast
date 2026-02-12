import { useState } from "react";

export default function ResultsPanel({ data }) {
  const [activeTab, setActiveTab] = useState("transcript");
  const { title, authors, abstract, transcript, audio_url } = data;

  const tabs = [
    { id: "transcript", label: "Transcript", icon: "📝" },
    ...(audio_url ? [{ id: "audio", label: "Audio", icon: "🎧" }] : []),
    { id: "paper", label: "Paper Info", icon: "📄" },
  ];

  return (
    <div
      className="w-full max-w-4xl mx-auto animate-fade-in-up space-y-6"
      style={{ animationDelay: "0.1s" }}
    >
      {/* Success banner */}
      <div className="glass p-5 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-green-500/15 flex items-center justify-center flex-shrink-0">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        </div>
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-white/90 truncate">
            {title || "Podcast Generated Successfully"}
          </h3>
          {authors && (
            <p className="text-sm text-white/40 truncate mt-0.5">{authors}</p>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 p-1 glass-sm w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? "bg-white/10 text-white shadow-sm"
                : "text-white/40 hover:text-white/70 hover:bg-white/[0.04]"
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="glass p-6 sm:p-8">
        {activeTab === "transcript" && (
          <TranscriptView transcript={transcript} />
        )}
        {activeTab === "audio" && audio_url && (
          <AudioPlayer audioUrl={audio_url} title={title} />
        )}
        {activeTab === "paper" && (
          <PaperInfo title={title} authors={authors} abstract={abstract} />
        )}
      </div>
    </div>
  );
}


function TranscriptView({ transcript }) {
  const [copied, setCopied] = useState(false);

  const lines = (transcript || "").split("\n");

  function handleCopy() {
    navigator.clipboard.writeText(transcript || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    const blob = new Blob([transcript || ""], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "podcast_transcript.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-base font-semibold text-white/80">
          Dialogue Transcript
        </h4>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="glass-sm glass-hover px-3 py-1.5 text-xs font-medium text-white/60 hover:text-white/90 flex items-center gap-1.5"
          >
            {copied ? (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                Copied
              </>
            ) : (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
                Copy
              </>
            )}
          </button>
          <button
            onClick={handleDownload}
            className="glass-sm glass-hover px-3 py-1.5 text-xs font-medium text-white/60 hover:text-white/90 flex items-center gap-1.5"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Download
          </button>
        </div>
      </div>

      <div className="max-h-[500px] overflow-y-auto pr-2 space-y-2">
        {lines.map((line, i) => {
          const isHost = line.startsWith("Host:");
          const isExpert = line.startsWith("Expert:");
          const isSpeaker = isHost || isExpert;

          if (!line.trim()) return null;

          return (
            <div
              key={i}
              className={`p-3 rounded-xl text-sm leading-relaxed ${
                isHost
                  ? "bg-indigo-500/8 border-l-2 border-indigo-400/40 ml-0 mr-8"
                  : isExpert
                  ? "bg-purple-500/8 border-l-2 border-purple-400/40 ml-8 mr-0"
                  : "text-white/40 text-xs"
              }`}
            >
              {isSpeaker ? (
                <>
                  <span
                    className={`text-xs font-bold uppercase tracking-wider ${
                      isHost ? "text-indigo-400" : "text-purple-400"
                    }`}
                  >
                    {isHost ? "Host" : "Expert"}
                  </span>
                  <p className="mt-1 text-white/75">
                    {line.replace(/^(Host|Expert):\s*/i, "")}
                  </p>
                </>
              ) : (
                <p>{line}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}


function AudioPlayer({ audioUrl, title }) {
  const fullUrl = `http://localhost:8000${audioUrl}`;

  function handleDownload() {
    const a = document.createElement("a");
    a.href = fullUrl;
    a.download = "podcast.wav";
    a.click();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        {/* Waveform animation */}
        <div className="flex items-center gap-1 h-8">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="waveform-bar"
              style={{ animationDelay: `${i * 0.15}s`, opacity: 0.4 + i * 0.08 }}
            />
          ))}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white/80 truncate">
            {title || "Generated Podcast"}
          </p>
          <p className="text-xs text-white/35 mt-0.5">AI-generated audio</p>
        </div>
      </div>

      {/* Native audio player */}
      <audio controls src={fullUrl} className="w-full rounded-lg" style={{ filter: "invert(1) hue-rotate(180deg)", opacity: 0.85 }}>
        Your browser does not support audio playback.
      </audio>

      <button onClick={handleDownload} className="btn-glow w-full flex items-center justify-center gap-2">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        Download Audio
      </button>
    </div>
  );
}


function PaperInfo({ title, authors, abstract }) {
  const fields = [
    { label: "Title", value: title },
    { label: "Authors", value: authors },
    { label: "Abstract", value: abstract },
  ];

  return (
    <div className="space-y-5">
      {fields.map(
        (f) =>
          f.value && (
            <div key={f.label}>
              <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">
                {f.label}
              </label>
              <p
                className={`text-sm leading-relaxed text-white/70 ${
                  f.label === "Abstract"
                    ? "glass-sm p-4 max-h-64 overflow-y-auto"
                    : ""
                }`}
              >
                {f.value}
              </p>
            </div>
          )
      )}
    </div>
  );
}
