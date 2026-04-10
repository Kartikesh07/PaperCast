import { useState, useRef, useEffect } from "react";
import { askQuestion } from "../api";

/* ── Icons ─────────────────────────────────────────────────────────── */

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      style={{ animation: "spin 1s linear infinite" }}>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

function BotIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      <circle cx="9" cy="16" r="1" /><circle cx="15" cy="16" r="1" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

const SUGGESTED_QUESTIONS = [
  "What problem does this paper solve?",
  "What is the main methodology used?",
  "What are the key results or findings?",
  "What are the limitations of this work?",
  "How does this compare to previous approaches?",
];

/* ── Main component ─────────────────────────────────────────────────── */

export default function PaperChat({ arxivId, paperTitle }) {
  const [messages, setMessages] = useState([]); // {role: 'user'|'assistant', content: string, error?: bool}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(questionText) {
    const question = (questionText ?? input).trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    // Build history for multi-turn context (exclude error messages)
    const history = messages
      .filter((m) => !m.error)
      .map(({ role, content }) => ({ role, content }));

    try {
      const { answer } = await askQuestion(arxivId, question, history);
      setMessages((prev) => [...prev, { role: "assistant", content: answer }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `⚠️ ${err.message}`, error: true },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "540px" }}>

      {/* ── Header ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: "10px",
        paddingBottom: "16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
        marginBottom: "16px",
      }}>
        <div style={{
          width: "34px", height: "34px", borderRadius: "10px",
          background: "linear-gradient(135deg, rgba(139,92,246,0.3), rgba(59,130,246,0.3))",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          <BotIcon />
        </div>
        <div>
          <p style={{ fontSize: "14px", fontWeight: 600, color: "rgba(255,255,255,0.85)", margin: 0 }}>
            Ask about this paper
          </p>
          <p style={{ fontSize: "12px", color: "rgba(255,255,255,0.35)", margin: 0, marginTop: "2px" }}>
            Powered by BM25 retrieval + Groq LLaMA
          </p>
        </div>
      </div>

      {/* ── Chat area ── */}
      <div style={{ flex: 1, overflowY: "auto", paddingRight: "4px" }} className="chat-scroll">

        {/* Empty state with suggested questions */}
        {isEmpty && (
          <div style={{ animation: "fadeInUp 0.4s ease" }}>
            <p style={{
              fontSize: "13px", color: "rgba(255,255,255,0.4)", marginBottom: "16px",
              textAlign: "center",
            }}>
              Ask anything about <span style={{ color: "rgba(255,255,255,0.65)" }}>
                {paperTitle ? `"${paperTitle.slice(0, 50)}${paperTitle.length > 50 ? "…" : ""}"` : "this paper"}
              </span>
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  style={{
                    textAlign: "left", background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)", borderRadius: "12px",
                    padding: "10px 14px", fontSize: "13px", color: "rgba(255,255,255,0.6)",
                    cursor: "pointer", transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(139,92,246,0.12)";
                    e.currentTarget.style.borderColor = "rgba(139,92,246,0.35)";
                    e.currentTarget.style.color = "rgba(255,255,255,0.85)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                    e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                    e.currentTarget.style.color = "rgba(255,255,255,0.6)";
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message bubbles */}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              flexDirection: msg.role === "user" ? "row-reverse" : "row",
              gap: "10px", alignItems: "flex-start",
              marginBottom: "16px",
              animation: "fadeInUp 0.3s ease",
            }}
          >
            {/* Avatar */}
            <div style={{
              width: "30px", height: "30px", borderRadius: "9px", flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: msg.role === "user"
                ? "rgba(99,102,241,0.25)"
                : "rgba(139,92,246,0.2)",
              color: msg.role === "user" ? "rgba(165,180,252,0.9)" : "rgba(196,181,253,0.9)",
            }}>
              {msg.role === "user" ? <UserIcon /> : <BotIcon />}
            </div>

            {/* Bubble */}
            <div style={{
              maxWidth: "80%",
              background: msg.role === "user"
                ? "rgba(99,102,241,0.15)"
                : msg.error
                  ? "rgba(239,68,68,0.1)"
                  : "rgba(255,255,255,0.05)",
              border: msg.role === "user"
                ? "1px solid rgba(99,102,241,0.25)"
                : msg.error
                  ? "1px solid rgba(239,68,68,0.2)"
                  : "1px solid rgba(255,255,255,0.07)",
              borderRadius: msg.role === "user" ? "16px 4px 16px 16px" : "4px 16px 16px 16px",
              padding: "12px 16px",
              fontSize: "14px", lineHeight: "1.65",
              color: msg.error ? "rgba(252,165,165,0.9)" : "rgba(255,255,255,0.78)",
              whiteSpace: "pre-wrap",
            }}>
              {msg.content}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {loading && (
          <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "16px" }}>
            <div style={{
              width: "30px", height: "30px", borderRadius: "9px",
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "rgba(139,92,246,0.2)", color: "rgba(196,181,253,0.9)", flexShrink: 0,
            }}>
              <BotIcon />
            </div>
            <div style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.07)",
              borderRadius: "4px 16px 16px 16px",
              padding: "12px 16px", display: "flex", gap: "5px", alignItems: "center",
            }}>
              {[0, 1, 2].map((i) => (
                <div key={i} style={{
                  width: "6px", height: "6px", borderRadius: "50%",
                  background: "rgba(139,92,246,0.7)",
                  animation: "dotPulse 1.2s ease-in-out infinite",
                  animationDelay: `${i * 0.2}s`,
                }} />
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ── */}
      <div style={{
        marginTop: "12px", display: "flex", gap: "10px", alignItems: "flex-end",
        borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "14px",
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about this paper…"
          rows={1}
          style={{
            flex: 1, resize: "none", background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px",
            padding: "10px 14px", fontSize: "14px", color: "rgba(255,255,255,0.85)",
            outline: "none", lineHeight: "1.5", maxHeight: "120px", overflowY: "auto",
            transition: "border-color 0.2s",
            fontFamily: "inherit",
          }}
          onFocus={(e) => e.target.style.borderColor = "rgba(139,92,246,0.5)"}
          onBlur={(e) => e.target.style.borderColor = "rgba(255,255,255,0.1)"}
          disabled={loading}
        />
        <button
          onClick={() => handleSend()}
          disabled={!input.trim() || loading}
          style={{
            width: "42px", height: "42px", borderRadius: "12px", flexShrink: 0,
            display: "flex", alignItems: "center", justifyContent: "center",
            background: !input.trim() || loading
              ? "rgba(255,255,255,0.06)"
              : "linear-gradient(135deg, rgba(139,92,246,0.8), rgba(99,102,241,0.8))",
            border: "1px solid rgba(255,255,255,0.1)",
            color: !input.trim() || loading ? "rgba(255,255,255,0.25)" : "white",
            cursor: !input.trim() || loading ? "not-allowed" : "pointer",
            transition: "all 0.2s",
          }}
        >
          {loading ? <SpinnerIcon /> : <SendIcon />}
        </button>
      </div>

      {/* Inline CSS for dot animation */}
      <style>{`
        @keyframes dotPulse {
          0%, 60%, 100% { transform: scale(1); opacity: 0.5; }
          30% { transform: scale(1.4); opacity: 1; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .chat-scroll::-webkit-scrollbar { width: 4px; }
        .chat-scroll::-webkit-scrollbar-track { background: transparent; }
        .chat-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
      `}</style>
    </div>
  );
}
