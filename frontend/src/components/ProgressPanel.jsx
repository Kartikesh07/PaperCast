const STAGES = [
  { key: "parse", label: "Parsing Paper", icon: "📄", range: [0, 0.15] },
  { key: "latex", label: "Converting Math", icon: "📐", range: [0.12, 0.18] },
  { key: "dialogue", label: "Generating Dialogue", icon: "💬", range: [0.15, 0.78] },
  { key: "postprocess", label: "Polishing Script", icon: "✨", range: [0.78, 0.82] },
  { key: "tts", label: "Generating Audio", icon: "🎙️", range: [0.82, 0.99] },
  { key: "done", label: "Complete", icon: "✅", range: [0.99, 1.0] },
];

function getActiveStage(progress) {
  for (let i = STAGES.length - 1; i >= 0; i--) {
    if (progress >= STAGES[i].range[0]) return i;
  }
  return 0;
}

export default function ProgressPanel({ progress, message, status }) {
  const pct = Math.round(progress * 100);
  const activeIdx = getActiveStage(progress);

  return (
    <div
      className="glass p-6 sm:p-8 w-full max-w-2xl mx-auto animate-fade-in-up"
      style={{ animationDelay: "0.15s" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white/90">Pipeline Progress</h3>
        <span className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent tabular-nums">
          {pct}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="progress-track mb-6">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>

      {/* Stage list */}
      <div className="space-y-3">
        {STAGES.map((stage, idx) => {
          const isDone = idx < activeIdx || status === "done";
          const isActive = idx === activeIdx && status !== "done";
          const isPending = idx > activeIdx && status !== "done";

          return (
            <div
              key={stage.key}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-300 ${
                isActive
                  ? "glass-sm border-indigo-500/30"
                  : isDone
                  ? "bg-white/[0.03]"
                  : "opacity-40"
              }`}
            >
              {/* Step indicator */}
              <div className="relative flex-shrink-0">
                {isDone ? (
                  <div className="w-7 h-7 rounded-full bg-green-500/20 flex items-center justify-center">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                ) : isActive ? (
                  <div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center">
                    <div className="w-3 h-3 rounded-full bg-indigo-400 animate-pulse-dot" />
                  </div>
                ) : (
                  <div className="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center">
                    <div className="w-2 h-2 rounded-full bg-white/20" />
                  </div>
                )}
              </div>

              {/* Label */}
              <span className="text-sm font-medium flex-1">
                {stage.icon} {stage.label}
              </span>

              {/* Status text */}
              {isActive && (
                <span className="text-xs text-indigo-300/70 truncate max-w-[180px]">
                  {message}
                </span>
              )}
              {isDone && (
                <span className="text-xs text-green-400/60">Done</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Error display */}
      {status === "error" && (
        <div className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
          <span className="font-semibold">Error:</span> {message}
        </div>
      )}
    </div>
  );
}
