import { useEffect, useRef } from "react";

const STAGES = ["profiling", "planning", "processing", "synthesizing", "executing", "done"];

const AGENT_META = {
  profiler:         { abbr: "PR", label: "Profiler",       color: "#10b981" },
  planner:          { abbr: "PL", label: "Planner",        color: "#f97316" },
  coordinator:      { abbr: "CO", label: "Coordinator",    color: "#facc15" },
  cleaner:          { abbr: "CL", label: "Cleaner",        color: "#f59e0b" },
  outlier:          { abbr: "OT", label: "Outlier",        color: "#f59e0b" },
  feature_engineer: { abbr: "FE", label: "Feature Eng.",  color: "#f59e0b" },
  validation:       { abbr: "VA", label: "Validation",     color: "#f59e0b" },
  code_synthesizer: { abbr: "SY", label: "Synthesizer",    color: "#06b6d4" },
  executor:         { abbr: "EX", label: "Executor",       color: "#ef4444" },
  system:           { abbr: "SY", label: "System",         color: "#94a3b8" },
};

export default function ProgressPanel({ events, status, finalState }) {
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  const currentStage = finalState?.status || status || "pending";
  const stageIdx = STAGES.indexOf(currentStage);
  const seenAgents = [...new Set(events.map((e) => e.agent).filter(Boolean))];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Stage progress bar */}
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
                    background: done ? "var(--accent)" : "rgba(255,255,255,0.1)",
                    transition: "background 0.5s ease", zIndex: 0,
                  }} />
                )}
                <div style={{
                  width: 28, height: 28, borderRadius: "50%", zIndex: 1,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.75rem", fontWeight: 700,
                  border: `2px solid ${done ? "var(--accent)" : active ? "var(--primary)" : "rgba(255,255,255,0.15)"}`,
                  background: done ? "var(--accent)" : active ? "rgba(249,115,22,0.28)" : "transparent",
                  color: done ? "#000" : active ? "var(--primary-glow)" : "var(--text-muted)",
                  animation: active && currentStage !== "done" ? "pulse-glow 1.5s infinite" : "none",
                  transition: "all 0.4s ease",
                  fontFamily: "var(--font-mono)",
                }}>
                  {done ? "✓" : i + 1}
                </div>
                <span style={{
                  fontSize: "0.63rem", marginTop: 5, textTransform: "capitalize",
                  color: done ? "var(--accent)" : active ? "var(--primary-glow)" : "var(--text-muted)",
                  fontWeight: active || done ? 600 : 400,
                }}>
                  {stage}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Agent activity chips */}
      {seenAgents.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {seenAgents.map((agentId) => {
            const meta = AGENT_META[agentId] || { abbr: agentId.slice(0, 2).toUpperCase(), label: agentId, color: "#94a3b8" };
            return (
              <div key={agentId} className="glass" style={{
                padding: "6px 12px",
                borderRadius: 50,
                display: "flex", alignItems: "center", gap: 8,
                border: `1px solid ${meta.color}33`,
                fontSize: "0.82rem", fontWeight: 500,
              }}>
                <span style={{
                  width: 20, height: 20, borderRadius: 4,
                  background: `${meta.color}22`, border: `1px solid ${meta.color}44`,
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.62rem",
                  color: meta.color, flexShrink: 0,
                }}>{meta.abbr}</span>
                <span style={{ color: meta.color }}>{meta.label}</span>
                <span style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: meta.color, boxShadow: `0 0 6px ${meta.color}`,
                  animation: "pulse-glow 1.5s infinite",
                }} />
              </div>
            );
          })}
        </div>
      )}

      {/* Terminal log */}
      <div className="glass" style={{
        borderRadius: 12, overflow: "hidden",
        border: "1px solid rgba(255,255,255,0.08)",
      }}>
        <div style={{
          background: "rgba(0,0,0,0.3)", padding: "10px 16px",
          display: "flex", alignItems: "center", gap: 8,
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}>
          <div style={{ display: "flex", gap: 6 }}>
            {["#ef4444", "#f59e0b", "#10b981"].map((c) => (
              <div key={c} style={{ width: 10, height: 10, borderRadius: "50%", background: c }} />
            ))}
          </div>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", marginLeft: 8 }}>
            mas-pipeline — live log
          </span>
          {status === "running" && (
            <span style={{
              marginLeft: "auto", fontSize: "0.72rem", color: "var(--accent)",
              display: "flex", alignItems: "center", gap: 5,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%", background: "var(--accent)",
                animation: "blink 1s infinite",
              }} />
              RUNNING
            </span>
          )}
        </div>

        <div ref={logRef} style={{
          height: 320, overflowY: "auto", padding: "12px 16px",
          fontFamily: "var(--font-mono)", fontSize: "0.8rem", lineHeight: 1.7,
          background: "rgba(0,0,0,0.2)",
        }}>
          {events.length === 0 ? (
            <span style={{ color: "var(--text-muted)" }}>
              Waiting for pipeline to start<span style={{ animation: "blink 1s infinite" }}>...</span>
            </span>
          ) : (
            events.map((evt, i) => <LogLine key={i} event={evt} />)
          )}
        </div>
      </div>

      {/* Result summary */}
      {finalState && (currentStage === "done" || currentStage === "error") && (
        <ResultSummary state={finalState} status={currentStage} />
      )}
    </div>
  );
}

function LogLine({ event }) {
  const meta = AGENT_META[event.agent] || { abbr: "SY", label: event.agent, color: "#94a3b8" };
  const isError = event.type === "error";
  const isSystem = event.type === "system" || event.type === "complete" || event.type === "done";

  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 2 }}>
      <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>
        {new Date(event.ts * 1000).toLocaleTimeString("en", { hour12: false })}
      </span>
      <span style={{
        color: meta.color, flexShrink: 0, minWidth: 110,
        fontWeight: 600,
      }}>
        {meta.label}
      </span>
      <span style={{
        color: isError ? "var(--danger)" : isSystem ? "var(--accent)" : "var(--text)",
        wordBreak: "break-word",
      }}>
        {event.message}
      </span>
    </div>
  );
}

function ResultSummary({ state, status }) {
  const isDone = status === "done";
  const outputCsv = state?.file_history?.output_csv;
  const script = state?.synthesized_code_path || state?.file_history?.script;
  const errors = state?.errors || [];
  const plan = state?.plan || {};
  const outputs = state?.agent_outputs || {};

  return (
    <div style={{
      borderRadius: 12, padding: 24,
      border: `1px solid ${isDone ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
      background: isDone ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10, flexShrink: 0,
          background: isDone ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
          border: `1px solid ${isDone ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.8rem",
          color: isDone ? "var(--accent)" : "var(--danger)",
        }}>
          {isDone ? "OK" : "ERR"}
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: "1.05rem", color: isDone ? "var(--accent)" : "var(--danger)" }}>
            {isDone ? "Pipeline Complete" : "Pipeline Failed"}
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Task type: <strong style={{ color: "var(--text)" }}>{state?.task_type || "—"}</strong>
            {" · "}Retries: <strong style={{ color: "var(--text)" }}>{state?.retry_count ?? 0}</strong>
          </div>
        </div>
      </div>

      {isDone && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {outputCsv && <OutputFile label="Preprocessed CSV" path={outputCsv} />}
          {script && <OutputFile label="Generated Script" path={script} />}
        </div>
      )}

      {errors.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: "0.8rem", color: "var(--danger)", fontWeight: 600, marginBottom: 6 }}>
            Errors ({errors.length}):
          </div>
          {errors.map((e, i) => (
            <div key={i} style={{
              fontFamily: "var(--font-mono)", fontSize: "0.75rem",
              color: "var(--danger)", opacity: 0.8, marginBottom: 2,
            }}>- {e}</div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--text)" }}>
          Planned Preprocessing Steps
        </div>

        <StepGroup title="Cleaning" steps={plan.cleaning_steps} />
        <StepGroup title="Outlier" steps={plan.outlier_steps} />
        <StepGroup title="Feature Engineering" steps={plan.feature_steps} />
        <StepGroup title="Validation" steps={plan.validation_steps} />
      </div>

      <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--text)" }}>
          Generated Agent Code
        </div>

        <CodeBlock title="Cleaner Agent" code={outputs.cleaner} />
        <CodeBlock title="Outlier Agent" code={outputs.outlier} />
        <CodeBlock title="Feature Engineer Agent" code={outputs.feature_engineer} />
        <CodeBlock title="Validation Agent" code={outputs.validation} />
      </div>
    </div>
  );
}

function OutputFile({ label, path }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "8px 14px",
      borderRadius: 8,
      background: "rgba(255,255,255,0.04)",
      border: "1px solid rgba(255,255,255,0.08)",
      fontFamily: "var(--font-mono)", fontSize: "0.78rem",
    }}>
      <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>{label}</span>
      <span style={{ color: "var(--text)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {path}
      </span>
    </div>
  );
}

function StepGroup({ title, steps }) {
  const safeSteps = Array.isArray(steps) ? steps : [];

  return (
    <div style={{
      borderRadius: 8,
      border: "1px solid rgba(255,255,255,0.08)",
      background: "rgba(255,255,255,0.03)",
      padding: "10px 12px",
    }}>
      <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: 6, color: "var(--primary-glow)" }}>
        {title}
      </div>

      {safeSteps.length === 0 ? (
        <div style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>No planned steps.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {safeSteps.map((step, idx) => {
            const action = step?.action || "step";
            const column = step?.column ? ` (${step.column})` : "";
            const reason = step?.reason ? ` — ${step.reason}` : "";
            return (
              <div key={`${title}-${idx}`} style={{ fontSize: "0.76rem", color: "var(--text)" }}>
                {idx + 1}. {action}{column}{reason}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CodeBlock({ title, code }) {
  const text = (code || "").trim();
  return (
    <details style={{
      borderRadius: 8,
      border: "1px solid rgba(255,255,255,0.08)",
      background: "rgba(0,0,0,0.18)",
      overflow: "hidden",
    }}>
      <summary style={{
        cursor: "pointer",
        listStyle: "none",
        padding: "10px 12px",
        fontSize: "0.82rem",
        fontWeight: 600,
        color: "var(--primary-glow)",
      }}>
        {title}
      </summary>
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
        <pre style={{
          margin: 0,
          padding: "10px 12px",
          maxHeight: 220,
          overflow: "auto",
          fontFamily: "var(--font-mono)",
          fontSize: "0.73rem",
          lineHeight: 1.5,
          color: text ? "var(--text)" : "var(--text-muted)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {text || "No code generated for this agent."}
        </pre>
      </div>
    </details>
  );
}
