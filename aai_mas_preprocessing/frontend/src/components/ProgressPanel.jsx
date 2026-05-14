import { useEffect, useRef, useState } from "react";

const API = "";

const STAGES = ["profiling", "planning", "processing", "synthesizing", "executing", "done"];

const AGENT_META = {
  profiler:         { abbr: "PR", label: "Profiler",          color: "#059669", role: "Analyses every column, infers ML task type, saves a JSON report." },
  planner:          { abbr: "PL", label: "Planner",           color: "#ea6c00", role: "Reads the profiler report and emits a structured cleaning/outlier/feature/validation plan." },
  coordinator:      { abbr: "CO", label: "Coordinator",       color: "#b45309", role: "Dispatches the plan to specialist agents in sequence; tolerates per-agent errors." },
  cleaner:          { abbr: "CL", label: "Cleaner",           color: "#0891b2", role: "Removes duplicates, imputes missing values, handles ID/datetime/free-text columns." },
  outlier:          { abbr: "OT", label: "Outlier",           color: "#7c3aed", role: "Detects and treats outliers per column (IQR, Z-score, IsolationForest)." },
  feature_engineer: { abbr: "FE", label: "Feature Engineer",  color: "#be185d", role: "Applies encoding (OHE, label, target), scaling (MinMax, Standard), log/cyclical transforms." },
  validation:       { abbr: "VA", label: "Validation",        color: "#0f766e", role: "Generates assertion-based post-processing checks wrapped in try/except." },
  code_synthesizer: { abbr: "SY", label: "Synthesizer",       color: "#0284c7", role: "Assembles all code snippets into a single executable .py script." },
  executor:         { abbr: "EX", label: "Executor",          color: "#dc2626", role: "Runs the script via subprocess; feeds tracebacks to the LLM for self-healing on failure." },
  system:           { abbr: "SY", label: "System",            color: "#78716c", role: "" },
};

// Which agents have plan steps + generated code
const SPECIALIST_AGENTS = [
  { id: "cleaner",          planKey: "cleaning_steps",    outputKey: "cleaner" },
  { id: "outlier",          planKey: "outlier_steps",     outputKey: "outlier" },
  { id: "feature_engineer", planKey: "feature_steps",     outputKey: "feature_engineer" },
  { id: "validation",       planKey: "validation_steps",  outputKey: "validation" },
];

export default function ProgressPanel({ events, status, finalState, runId }) {
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  const currentStage = finalState?.status || status || "pending";
  const stageIdx = STAGES.indexOf(currentStage);
  const isDone = currentStage === "done" || currentStage === "error";
  const seenAgents = [...new Set(events.map((e) => e.agent).filter(Boolean))];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Stage progress bar ───────────────────────────────────────────── */}
      <div className="glass progress-stage-shell" style={{ borderRadius: 12, padding: "20px 24px" }}>
        <div className="progress-stage-row" style={{ display: "flex", justifyContent: "space-between" }}>
          {STAGES.map((stage, i) => {
            const done = i < stageIdx || currentStage === "done";
            const active = stage === currentStage;
            return (
              <div key={stage} style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, position: "relative" }}>
                {i < STAGES.length - 1 && (
                  <div style={{
                    position: "absolute", top: 14, left: "50%", right: "-50%",
                    height: 2,
                    background: done ? "var(--primary)" : "rgba(180,80,0,0.12)",
                    transition: "background 0.5s ease", zIndex: 0,
                  }} />
                )}
                <div style={{
                  width: 28, height: 28, borderRadius: "50%", zIndex: 1,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.75rem", fontWeight: 700,
                  border: `2px solid ${done ? "var(--primary)" : active ? "var(--primary-glow)" : "rgba(180,80,0,0.2)"}`,
                  background: done ? "var(--primary)" : active ? "rgba(234,108,0,0.12)" : "transparent",
                  color: done ? "#fff" : active ? "var(--primary)" : "var(--text-muted)",
                  animation: active && currentStage !== "done" ? "pulse-glow 1.5s infinite" : "none",
                  transition: "all 0.4s ease",
                  fontFamily: "var(--font-mono)",
                }}>
                  {done ? "✓" : i + 1}
                </div>
                <span style={{
                  fontSize: "0.63rem", marginTop: 5, textTransform: "capitalize",
                  color: done ? "var(--primary)" : active ? "var(--primary-glow)" : "var(--text-muted)",
                  fontWeight: active || done ? 600 : 400,
                }}>
                  {stage}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Live agent chips (running) OR agent cards (done) ─────────────── */}
      {!isDone && seenAgents.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {seenAgents.map((agentId) => {
            const meta = AGENT_META[agentId] || { abbr: agentId.slice(0, 2).toUpperCase(), label: agentId, color: "#78716c" };
            return (
              <div key={agentId} className="glass" style={{
                padding: "5px 12px", borderRadius: 50,
                display: "flex", alignItems: "center", gap: 8,
                border: `1px solid ${meta.color}28`, fontSize: "0.82rem", fontWeight: 500,
              }}>
                <span style={{
                  width: 20, height: 20, borderRadius: 4,
                  background: `${meta.color}14`, border: `1px solid ${meta.color}30`,
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.62rem",
                  color: meta.color, flexShrink: 0,
                }}>{meta.abbr}</span>
                <span style={{ color: meta.color }}>{meta.label}</span>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: meta.color, animation: "pulse-glow 1.5s infinite" }} />
              </div>
            );
          })}
        </div>
      )}

      {/* ── Terminal log — always dark ────────────────────────────────────── */}
      <div className="glass code-terminal" style={{ borderRadius: 12, overflow: "hidden" }}>
        <div className="code-terminal-header" style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {["#ef4444", "#f59e0b", "#10b981"].map((c) => (
              <div key={c} style={{ width: 10, height: 10, borderRadius: "50%", background: c }} />
            ))}
          </div>
          <span style={{ fontSize: "0.8rem", color: "#fef3c7", fontFamily: "var(--font-mono)", marginLeft: 8, opacity: 0.7 }}>
            mas-pipeline — live log
          </span>
          {status === "running" && (
            <span style={{ marginLeft: "auto", fontSize: "0.72rem", color: "#34d399", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d399", animation: "blink 1s infinite" }} />
              RUNNING
            </span>
          )}
        </div>
        <div ref={logRef} style={{
          height: 300, overflowY: "auto", padding: "12px 16px",
          fontFamily: "var(--font-mono)", fontSize: "0.8rem", lineHeight: 1.7,
          background: "rgba(0,0,0,0.15)",
        }}>
          {events.length === 0 ? (
            <span style={{ color: "#a78bfa", opacity: 0.6 }}>
              Waiting for pipeline to start<span style={{ animation: "blink 1s infinite" }}>...</span>
            </span>
          ) : (
            events.map((evt, i) => <LogLine key={i} event={evt} />)
          )}
        </div>
      </div>

      {/* ── Result summary (only after done/error) ───────────────────────── */}
      {finalState && isDone && (
        <ResultSummary state={finalState} status={currentStage} runId={runId} />
      )}
    </div>
  );
}

/* ── Log line ──────────────────────────────────────────────────────────────── */
function LogLine({ event }) {
  const meta = AGENT_META[event.agent] || { abbr: "SY", label: event.agent, color: "#78716c" };
  const isError  = event.type === "error";
  const isSystem = event.type === "system" || event.type === "complete" || event.type === "done";
  const agentColor = isError ? "#f87171" : isSystem ? "#34d399" : meta.color;
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 2 }}>
      <span style={{ color: "#6b7280", flexShrink: 0 }}>
        {new Date(event.ts * 1000).toLocaleTimeString("en", { hour12: false })}
      </span>
      <span style={{ color: agentColor, flexShrink: 0, minWidth: 110, fontWeight: 600 }}>
        {meta.label}
      </span>
      <span style={{ color: isError ? "#f87171" : isSystem ? "#d1fae5" : "#fef3c7", wordBreak: "break-word" }}>
        {event.message}
      </span>
    </div>
  );
}

/* ── Result summary ────────────────────────────────────────────────────────── */
function ResultSummary({ state, status, runId }) {
  const isDone    = status === "done";
  const outputCsv = state?.file_history?.output_csv;
  const errors    = state?.errors || [];
  const plan      = state?.plan || {};
  const outputs   = state?.agent_outputs || {};
  const report    = state?.comparison_report || null;

  const handleDownload = () => window.open(`${API}/api/download/${runId}`, "_blank");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Status banner + download */}
      <div style={{
        borderRadius: 12, padding: 20,
        border: `1px solid ${isDone ? "rgba(5,150,105,0.25)" : "rgba(220,38,38,0.25)"}`,
        background: isDone ? "rgba(5,150,105,0.05)" : "rgba(220,38,38,0.05)",
        display: "flex", alignItems: "center", gap: 14,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10, flexShrink: 0,
          background: isDone ? "rgba(5,150,105,0.10)" : "rgba(220,38,38,0.10)",
          border: `1px solid ${isDone ? "rgba(5,150,105,0.25)" : "rgba(220,38,38,0.25)"}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.8rem",
          color: isDone ? "#059669" : "#dc2626",
        }}>
          {isDone ? "OK" : "ERR"}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: "1.05rem", color: isDone ? "#059669" : "#dc2626" }}>
            {isDone ? "Pipeline Complete" : "Pipeline Failed"}
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Task type: <strong style={{ color: "var(--text)" }}>{state?.task_type || "—"}</strong>
            {" · "}Retries: <strong style={{ color: "var(--text)" }}>{state?.retry_count ?? 0}</strong>
          </div>
        </div>
        {isDone && runId && outputCsv && (
          <button onClick={handleDownload} className="btn btn-primary" style={{ padding: "10px 20px", fontSize: "0.85rem", flexShrink: 0 }}>
            ↓ Download CSV
          </button>
        )}
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div style={{
          borderRadius: 10, padding: "12px 16px",
          background: "rgba(220,38,38,0.04)", border: "1px solid rgba(220,38,38,0.18)",
        }}>
          <div style={{ fontSize: "0.8rem", color: "#dc2626", fontWeight: 600, marginBottom: 6 }}>
            Errors ({errors.length}):
          </div>
          {errors.map((e, i) => (
            <div key={i} style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#dc2626", opacity: 0.8, marginBottom: 2 }}>- {e}</div>
          ))}
        </div>
      )}

      {/* Comparison report */}
      {report && !report.error && <ComparisonReport report={report} />}

      {/* ── Agent cards — one per specialist agent ─────────────────────── */}
      <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--text)", marginTop: 4 }}>
        Agent Contributions
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {SPECIALIST_AGENTS.map(({ id, planKey, outputKey }) => (
          <AgentCard
            key={id}
            agentId={id}
            steps={plan[planKey]}
            code={outputs[outputKey]}
          />
        ))}
      </div>
    </div>
  );
}

/* ── Agent card (expandable) ───────────────────────────────────────────────── */
function AgentCard({ agentId, steps, code }) {
  const [open, setOpen] = useState(false);
  const meta      = AGENT_META[agentId];
  const safeSteps = Array.isArray(steps) ? steps : [];
  const codeText  = (code || "").trim();
  const hasContent = safeSteps.length > 0 || codeText.length > 0;

  return (
    <div className="glass" style={{
      borderRadius: 12,
      border: `1px solid ${meta.color}22`,
      overflow: "hidden",
    }}>
      {/* Card header — always visible, clickable */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 14,
          padding: "14px 18px", background: "transparent", border: "none",
          cursor: "pointer", textAlign: "left",
        }}
      >
        {/* Agent badge */}
        <div style={{
          width: 38, height: 38, borderRadius: 10, flexShrink: 0,
          background: `${meta.color}14`, border: `1px solid ${meta.color}30`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: "0.72rem",
          color: meta.color,
        }}>{meta.abbr}</div>

        {/* Agent name + role */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: "0.92rem", color: "var(--text)" }}>{meta.label}</div>
          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 1 }}>{meta.role}</div>
        </div>

        {/* Step count badge */}
        <div style={{
          padding: "3px 10px", borderRadius: 50, flexShrink: 0,
          background: safeSteps.length > 0 ? `${meta.color}12` : "rgba(0,0,0,0.04)",
          border: `1px solid ${safeSteps.length > 0 ? meta.color + "28" : "rgba(0,0,0,0.08)"}`,
          fontSize: "0.75rem", fontWeight: 600,
          color: safeSteps.length > 0 ? meta.color : "var(--text-muted)",
        }}>
          {safeSteps.length > 0 ? `${safeSteps.length} step${safeSteps.length !== 1 ? "s" : ""}` : "0 steps"}
        </div>

        {/* Code badge */}
        {codeText.length > 0 && (
          <div style={{
            padding: "3px 10px", borderRadius: 50, flexShrink: 0,
            background: "rgba(0,0,0,0.04)", border: "1px solid rgba(0,0,0,0.08)",
            fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)",
          }}>
            code
          </div>
        )}

        {/* Chevron */}
        {hasContent && (
          <span style={{
            fontSize: "0.75rem", color: "var(--text-muted)", flexShrink: 0,
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}>▼</span>
        )}
      </button>

      {/* Expanded body */}
      {open && hasContent && (
        <div style={{ borderTop: `1px solid ${meta.color}18`, padding: "14px 18px", display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Plan steps */}
          {safeSteps.length > 0 && (
            <div>
              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: meta.color, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Planned Steps
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                {safeSteps.map((step, idx) => {
                  const action   = step?.action   || "step";
                  const column   = step?.column   ? ` (${step.column})` : "";
                  const strategy = step?.strategy ? ` · strategy: ${step.strategy}` : "";
                  const reason   = step?.reason   ? ` — ${step.reason}` : "";
                  return (
                    <div key={idx} style={{
                      display: "flex", gap: 10, alignItems: "flex-start",
                      padding: "6px 10px", borderRadius: 7,
                      background: `${meta.color}08`,
                      border: `1px solid ${meta.color}14`,
                      fontSize: "0.78rem",
                    }}>
                      <span style={{
                        width: 20, height: 20, borderRadius: 5, flexShrink: 0,
                        background: `${meta.color}18`, border: `1px solid ${meta.color}28`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.66rem",
                        color: meta.color,
                      }}>{idx + 1}</span>
                      <div>
                        <span style={{ fontWeight: 600, color: "var(--text)" }}>{action}</span>
                        <span style={{ color: meta.color }}>{column}</span>
                        <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>{strategy}</span>
                        {reason && <div style={{ color: "var(--text-muted)", marginTop: 1 }}>{reason}</div>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Generated code */}
          {codeText.length > 0 && (
            <div>
              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: meta.color, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Generated Code
              </div>
              <div style={{ borderRadius: 8, overflow: "hidden", border: `1px solid ${meta.color}22` }}>
                <div style={{
                  background: "#160e00", padding: "8px 14px",
                  borderBottom: `1px solid ${meta.color}22`,
                  display: "flex", alignItems: "center", gap: 8,
                }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%", background: meta.color,
                  }} />
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "#fef3c7", opacity: 0.6 }}>
                    {agentId}_snippet.py
                  </span>
                </div>
                <pre style={{
                  margin: 0, padding: "12px 14px",
                  maxHeight: 280, overflowY: "auto",
                  background: "#160e00",
                  fontFamily: "var(--font-mono)", fontSize: "0.73rem",
                  lineHeight: 1.6, color: "#fef3c7",
                  whiteSpace: "pre-wrap", wordBreak: "break-word",
                }}>
                  {codeText}
                </pre>
              </div>
            </div>
          )}

          {!safeSteps.length && !codeText.length && (
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>No output from this agent.</div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Comparison Report ────────────────────────────────────────────────────── */
function ComparisonReport({ report }) {
  const { raw, processed, changes } = report;

  const statRow = (label, before, after, lowerIsBetter = false) => {
    const diff     = after - before;
    const improved = lowerIsBetter ? diff < 0 : diff > 0;
    const neutral  = diff === 0;
    const color    = neutral ? "var(--text-muted)" : improved ? "#059669" : "#dc2626";
    const sign     = diff > 0 ? "+" : "";
    return (
      <tr key={label}>
        <td style={{ padding: "7px 12px", color: "var(--text-muted)", fontSize: "0.82rem" }}>{label}</td>
        <td style={{ padding: "7px 12px", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>{before.toLocaleString()}</td>
        <td style={{ padding: "7px 12px", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>{after.toLocaleString()}</td>
        <td style={{ padding: "7px 12px", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "0.82rem", color, fontWeight: 600 }}>
          {neutral ? "—" : `${sign}${diff.toLocaleString()}`}
        </td>
      </tr>
    );
  };

  return (
    <SectionCard title="Dataset Comparison Report">
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Metric", "Before", "After", "Δ Change"].map((h) => (
                <th key={h} style={{
                  padding: "8px 12px", textAlign: h === "Metric" ? "left" : "right",
                  fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)",
                  textTransform: "uppercase", letterSpacing: "0.06em",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {statRow("Rows",        raw.rows,        processed.rows,        false)}
            {statRow("Columns",     raw.cols,        processed.cols,        false)}
            {statRow("Null values", raw.total_nulls, processed.total_nulls, true)}
          </tbody>
        </table>
      </div>

      {(changes.added_columns.length > 0 || changes.removed_columns.length > 0) && (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 4 }}>
          {changes.added_columns.length > 0 && <TagGroup label="Added columns"   tags={changes.added_columns}   color="#059669" />}
          {changes.removed_columns.length > 0 && <TagGroup label="Removed columns" tags={changes.removed_columns} color="#dc2626" />}
        </div>
      )}

      <PerColumnReport raw={raw.columns} processed={processed.columns} />
    </SectionCard>
  );
}

function TagGroup({ label, tags, color }) {
  return (
    <div style={{ flex: "1 1 200px" }}>
      <div style={{ fontSize: "0.75rem", fontWeight: 600, color, marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {tags.map((t) => (
          <span key={t} style={{
            padding: "2px 10px", borderRadius: 50,
            background: `${color}10`, border: `1px solid ${color}28`,
            color, fontSize: "0.75rem", fontFamily: "var(--font-mono)",
          }}>{t}</span>
        ))}
      </div>
    </div>
  );
}

function PerColumnReport({ raw, processed }) {
  const sharedNumeric = Object.keys(raw).filter(
    (col) => col in processed && raw[col].mean !== undefined && processed[col].mean !== undefined
  );
  if (sharedNumeric.length === 0) return null;
  return (
    <details style={{ marginTop: 4 }}>
      <summary style={{ cursor: "pointer", listStyle: "none", fontSize: "0.82rem", fontWeight: 600, color: "var(--primary)", padding: "4px 0" }}>
        ▸ Per-column numeric stats ({sharedNumeric.length} columns)
      </summary>
      <div style={{ marginTop: 8, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Column", "Nulls ↓", "Mean →", "Std →", "Min →", "Max →"].map((h) => (
                <th key={h} style={{ padding: "6px 10px", textAlign: h === "Column" ? "left" : "right", fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600, whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sharedNumeric.map((col) => {
              const r = raw[col];
              const p = processed[col];
              const fmt = (v) => v == null ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 3 });
              const nullDelta = p.nulls - r.nulls;
              const nullColor = nullDelta < 0 ? "#059669" : nullDelta > 0 ? "#dc2626" : "var(--text-muted)";
              return (
                <tr key={col} style={{ borderBottom: "1px solid rgba(180,80,0,0.07)" }}>
                  <td style={{ padding: "6px 10px", fontFamily: "var(--font-mono)", color: "var(--text)", fontWeight: 500 }}>{col}</td>
                  <td style={{ padding: "6px 10px", textAlign: "right", fontFamily: "var(--font-mono)", color: nullColor }}>{r.nulls} → {p.nulls}</td>
                  <td style={{ padding: "6px 10px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text)" }}>{fmt(r.mean)} → {fmt(p.mean)}</td>
                  <td style={{ padding: "6px 10px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text)" }}>{fmt(r.std)} → {fmt(p.std)}</td>
                  <td style={{ padding: "6px 10px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text)" }}>{fmt(r.min)} → {fmt(p.min)}</td>
                  <td style={{ padding: "6px 10px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text)" }}>{fmt(r.max)} → {fmt(p.max)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/* ── Shared helpers ────────────────────────────────────────────────────────── */
function SectionCard({ title, children }) {
  return (
    <div className="glass" style={{ borderRadius: 12, padding: 20 }}>
      <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--text)", marginBottom: 12 }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>{children}</div>
    </div>
  );
}
