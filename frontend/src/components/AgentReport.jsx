import { useState } from "react";

/* ── Small display helpers ─────────────────────────────────────────── */

const PAPER_TYPE_META = {
  empirical:   { icon: "🧪", label: "Empirical Study",    color: "#34d399" },
  survey:      { icon: "📚", label: "Literature Survey",  color: "#60a5fa" },
  theoretical: { icon: "📐", label: "Theoretical Paper", color: "#a78bfa" },
  application: { icon: "🛠️", label: "Applied Research",  color: "#fbbf24" },
};

const DEPTH_META = {
  full:   { label: "Full Coverage",   dot: "#34d399", bg: "rgba(52,211,153,0.1)",  border: "rgba(52,211,153,0.25)"  },
  brief:  { label: "Brief",          dot: "#fbbf24", bg: "rgba(251,191,36,0.1)",  border: "rgba(251,191,36,0.25)"  },
  skip:   { label: "Skipped",        dot: "#6b7280", bg: "rgba(107,114,128,0.08)", border: "rgba(107,114,128,0.15)" },
  bridge: { label: "Bridge",         dot: "#818cf8", bg: "rgba(129,140,248,0.08)", border: "rgba(129,140,248,0.15)" },
};

const SEVERITY_META = {
  none:  { icon: "✅", label: "Passed",      color: "#34d399", bg: "rgba(52,211,153,0.08)",  border: "rgba(52,211,153,0.2)"  },
  minor: { icon: "⚠️", label: "Minor",       color: "#fbbf24", bg: "rgba(251,191,36,0.08)",  border: "rgba(251,191,36,0.2)"  },
  major: { icon: "❌", label: "Rewritten",   color: "#f87171", bg: "rgba(248,113,113,0.08)", border: "rgba(248,113,113,0.2)" },
};

function Tag({ text, color, bg, border }) {
  return (
    <span style={{
      fontSize: "11px", fontWeight: 600, letterSpacing: "0.05em",
      padding: "2px 8px", borderRadius: "6px",
      color, background: bg, border: `1px solid ${border}`,
    }}>
      {text}
    </span>
  );
}

function SectionRow({ name, depth, critiqueSeverity, issues, regenerated }) {
  const [open, setOpen] = useState(false);
  const dm = DEPTH_META[depth] || DEPTH_META.full;
  const sm = critiqueSeverity ? (SEVERITY_META[critiqueSeverity] || SEVERITY_META.none) : null;
  const hasIssues = issues && issues.length > 0;

  return (
    <div style={{
      borderRadius: "10px", border: "1px solid rgba(255,255,255,0.07)",
      background: "rgba(255,255,255,0.03)", overflow: "hidden",
      marginBottom: "8px",
    }}>
      <div
        onClick={() => hasIssues && setOpen(!open)}
        style={{
          display: "flex", alignItems: "center", gap: "10px",
          padding: "10px 14px",
          cursor: hasIssues ? "pointer" : "default",
        }}
      >
        {/* Depth dot */}
        <span style={{
          width: "8px", height: "8px", borderRadius: "50%",
          background: dm.dot, flexShrink: 0,
        }} />

        {/* Section name */}
        <span style={{ flex: 1, fontSize: "13px", color: "rgba(255,255,255,0.75)", fontWeight: 500 }}>
          {name}
        </span>

        {/* Depth badge */}
        <Tag text={dm.label} color={dm.dot} bg={dm.bg} border={dm.border} />

        {/* Critic badge */}
        {sm && (
          <Tag
            text={`${sm.icon} ${regenerated ? "Rewritten" : sm.label}`}
            color={sm.color} bg={sm.bg} border={sm.border}
          />
        )}

        {/* Expand arrow */}
        {hasIssues && (
          <span style={{
            fontSize: "10px", color: "rgba(255,255,255,0.3)",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}>▶</span>
        )}
      </div>

      {/* Issues panel */}
      {open && hasIssues && (
        <div style={{
          padding: "10px 14px 12px",
          borderTop: "1px solid rgba(255,255,255,0.06)",
          background: "rgba(248,113,113,0.04)",
        }}>
          <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)", marginBottom: "6px", fontWeight: 600, letterSpacing: "0.05em" }}>
            CRITIC ISSUES
          </p>
          {issues.map((issue, i) => (
            <p key={i} style={{ fontSize: "12px", color: "rgba(248,113,113,0.8)", marginBottom: "4px" }}>
              • {issue}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}


/* ── Main AgentReport component ────────────────────────────────────── */

export default function AgentReport({ agentReport }) {
  if (!agentReport) {
    return (
      <div style={{ textAlign: "center", padding: "40px 20px", color: "rgba(255,255,255,0.3)", fontSize: "14px" }}>
        Agent report not available for this paper.<br />
        <span style={{ fontSize: "12px" }}>Re-process with <code style={{ color: "rgba(255,255,255,0.5)" }}>AGENTIC_ENABLED=true</code> to see planning data.</span>
      </div>
    );
  }

  const plan = agentReport.podcast_plan;
  const criticReports = agentReport.critic_reports || {};

  const typeMeta = plan ? (PAPER_TYPE_META[plan.paper_type] || PAPER_TYPE_META.empirical) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>

      {/* ── Episode Plan Card ── */}
      {plan && (
        <div>
          <p style={{ fontSize: "11px", fontWeight: 700, color: "rgba(255,255,255,0.3)", letterSpacing: "0.08em", marginBottom: "12px" }}>
            📋 EPISODE PLAN
          </p>

          {/* Type + Duration row */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", marginBottom: "14px", alignItems: "center" }}>
            {typeMeta && (
              <div style={{
                display: "flex", alignItems: "center", gap: "8px",
                padding: "8px 14px", borderRadius: "10px",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.08)",
              }}>
                <span style={{ fontSize: "18px" }}>{typeMeta.icon}</span>
                <div>
                  <p style={{ fontSize: "12px", fontWeight: 700, color: typeMeta.color, margin: 0 }}>{typeMeta.label}</p>
                  <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.35)", margin: 0 }}>{plan.paper_type}</p>
                </div>
              </div>
            )}
            <div style={{
              display: "flex", alignItems: "center", gap: "8px",
              padding: "8px 14px", borderRadius: "10px",
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}>
              <span style={{ fontSize: "18px" }}>🕐</span>
              <div>
                <p style={{ fontSize: "12px", fontWeight: 700, color: "rgba(255,255,255,0.8)", margin: 0 }}>~{plan.target_minutes} min</p>
                <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.35)", margin: 0, textTransform: "capitalize" }}>{plan.target_duration} episode</p>
              </div>
            </div>
            <div style={{
              display: "flex", alignItems: "center", gap: "8px",
              padding: "8px 14px", borderRadius: "10px",
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}>
              <span style={{ fontSize: "18px" }}>📑</span>
              <div>
                <p style={{ fontSize: "12px", fontWeight: 700, color: "rgba(255,255,255,0.8)", margin: 0 }}>
                  {(plan.sections || []).filter(s => s.depth === "full").length} full ·{" "}
                  {(plan.sections || []).filter(s => s.depth === "brief").length} brief ·{" "}
                  {(plan.sections || []).filter(s => s.depth === "skip").length} skipped
                </p>
                <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.35)", margin: 0 }}>sections</p>
              </div>
            </div>
          </div>

          {/* Episode angle */}
          {plan.episode_angle && (
            <div style={{
              padding: "12px 16px", borderRadius: "10px",
              background: "rgba(129,140,248,0.08)",
              border: "1px solid rgba(129,140,248,0.2)",
              marginBottom: "18px",
            }}>
              <p style={{ fontSize: "11px", fontWeight: 700, color: "rgba(129,140,248,0.7)", marginBottom: "4px", letterSpacing: "0.06em" }}>
                🎙️ EPISODE ANGLE
              </p>
              <p style={{ fontSize: "13px", color: "rgba(255,255,255,0.7)", fontStyle: "italic", margin: 0, lineHeight: "1.5" }}>
                "{plan.episode_angle}"
              </p>
            </div>
          )}

          {/* Section plan rows */}
          <p style={{ fontSize: "11px", fontWeight: 700, color: "rgba(255,255,255,0.3)", letterSpacing: "0.08em", marginBottom: "10px" }}>
            🔍 CRITIC REVIEW BY SECTION
          </p>
          {(plan.sections || []).map((sec) => {
            const cr = criticReports[sec.display] || null;
            return (
              <SectionRow
                key={sec.key}
                name={sec.display}
                depth={sec.depth}
                critiqueSeverity={cr ? cr.severity : null}
                issues={cr ? cr.issues : []}
                regenerated={cr ? cr.regenerated : false}
              />
            );
          })}
        </div>
      )}

      {/* ── Critic summary ── */}
      {Object.keys(criticReports).length > 0 && (
        <div style={{
          padding: "12px 16px", borderRadius: "10px",
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}>
          <p style={{ fontSize: "11px", fontWeight: 700, color: "rgba(255,255,255,0.3)", letterSpacing: "0.08em", marginBottom: "10px" }}>
            📊 CRITIC SUMMARY
          </p>
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
            {[
              { label: "Passed",   value: Object.values(criticReports).filter(r => r.passed && !r.regenerated).length, color: "#34d399" },
              { label: "Rewritten", value: Object.values(criticReports).filter(r => r.regenerated).length, color: "#fbbf24" },
              { label: "Issues",   value: Object.values(criticReports).reduce((sum, r) => sum + (r.issues||[]).length, 0), color: "#f87171" },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ textAlign: "center" }}>
                <p style={{ fontSize: "24px", fontWeight: 700, color, margin: 0, lineHeight: 1 }}>{value}</p>
                <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.35)", margin: "4px 0 0", letterSpacing: "0.05em" }}>{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
