import { useState, useCallback } from "react";
import Header from "./components/Header";
import Hero from "./components/Hero";
import InputPanel from "./components/InputPanel";
import ProgressPanel from "./components/ProgressPanel";
import ResultsPanel from "./components/ResultsPanel";
import Footer from "./components/Footer";
import { startGeneration, streamJobProgress, fetchJobStatus } from "./api";

// App states: idle → loading → done | error
function App() {
  const [phase, setPhase] = useState("idle"); // idle | loading | done | error
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = useCallback(async (params) => {
    setPhase("loading");
    setProgress(0);
    setMessage("Starting pipeline…");
    setResult(null);
    setError(null);

    try {
      // Kick off the job
      const { job_id } = await startGeneration(params);

      // Stream real-time updates from SSE
      const final = await streamJobProgress(job_id, (data) => {
        setProgress(data.progress || 0);
        setMessage(data.message || "");
      });

      if (final.status === "error") {
        setPhase("error");
        setError(final.error || final.message || "Unknown error");
        return;
      }

      // If the SSE final payload has results, use them;
      // otherwise poll once more.
      let resultData = final;
      if (!final.transcript) {
        resultData = await fetchJobStatus(job_id);
      }

      setResult(resultData);
      setPhase("done");
    } catch (err) {
      setPhase("error");
      setError(err.message);
      setMessage(`Error: ${err.message}`);
    }
  }, []);

  const handleReset = useCallback(() => {
    setPhase("idle");
    setProgress(0);
    setMessage("");
    setResult(null);
    setError(null);
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 px-4 sm:px-6 pb-8">
        {/* Hero — only on idle */}
        {phase === "idle" && <Hero />}

        {/* Input form — idle or error */}
        {(phase === "idle" || phase === "error") && (
          <div className="mt-2">
            <InputPanel onSubmit={handleSubmit} isLoading={false} />
            {phase === "error" && error && (
              <div className="max-w-2xl mx-auto mt-4 p-4 glass rounded-xl bg-red-500/10 border-red-500/20 text-red-300 text-sm animate-fade-in-up">
                <div className="flex items-start gap-3">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0 mt-0.5">
                    <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
                  </svg>
                  <div>
                    <p className="font-semibold mb-1">Generation Failed</p>
                    <p className="text-red-300/70">{error}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Loading progress */}
        {phase === "loading" && (
          <div className="mt-12">
            <ProgressPanel
              progress={progress}
              message={message}
              status="running"
            />
            <p className="text-center text-xs text-white/25 mt-4">
              This may take a few minutes depending on paper length
            </p>
          </div>
        )}

        {/* Results */}
        {phase === "done" && result && (
          <div className="mt-8">
            <ResultsPanel data={result} />
            <div className="flex justify-center mt-8">
              <button
                onClick={handleReset}
                className="glass-sm glass-hover px-6 py-3 text-sm font-medium text-white/60 hover:text-white/90 flex items-center gap-2"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="1 4 1 10 7 10" />
                  <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
                </svg>
                Generate Another
              </button>
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default App;
