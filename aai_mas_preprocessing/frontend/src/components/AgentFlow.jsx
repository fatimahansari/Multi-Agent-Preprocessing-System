import { useState } from "react";

const AGENTS = [
  {
    id: "profiler",
    label: "Profiler",
    abbr: "PR",
    color: "#10b981",
    description: "Deterministic. Loads the CSV, computes per-column statistics (dtype, nulls, skewness, cardinality), infers ML task type (regression / classification / forecasting), and saves a compact report JSON.",
    badge: "No LLM",
    badgeColor: "#10b981",
  },
  {
    id: "planner",
    label: "Planner",
    abbr: "PL",
    color: "#f97316",
    description: "LLM-powered. Reads the profiler report and outputs a structured JSON plan with four sections: cleaning_steps, outlier_steps, feature_steps, and validation_steps. Uses Claude with a data-expert system prompt.",
    badge: "LLM",
    badgeColor: "#f97316",
  },
  {
    id: "coordinator",
    label: "Coordinator",
    abbr: "CO",
    color: "#facc15",
    description: "No LLM. Dispatches the plan to the four specialist agents in the correct sequence, collecting their generated code snippets. Tolerates per-agent errors — the pipeline continues even if one specialist fails.",
    badge: "Orchestrator",
    badgeColor: "#facc15",
  },
  {
    id: "cleaner",
    label: "Cleaner",
    abbr: "CL",
    color: "#f59e0b",
    description: "LLM-powered. Generates pandas code for duplicate removal, median/mode null imputation, ID and index column dropping, datetime feature extraction (year/month/day/sin/cos), and free-text column removal.",
    badge: "LLM",
    badgeColor: "#f97316",
  },
  {
    id: "outlier",
    label: "Outlier",
    abbr: "OT",
    color: "#f59e0b",
    description: "LLM-powered. Generates per-column outlier treatment code supporting three methods: IQR (clip/remove/flag), Z-score (clip/remove/flag), and IsolationForest (flag + remove). Never modifies the target column.",
    badge: "LLM",
    badgeColor: "#f97316",
  },
  {
    id: "feature_engineer",
    label: "Feature Eng.",
    abbr: "FE",
    color: "#f59e0b",
    description: "LLM-powered. Generates encoding (OHE, LabelEncoder, target encoding), scaling (MinMax, Standard), log1p transforms for skewed columns, and cyclical sin/cos encodings for temporal features.",
    badge: "LLM",
    badgeColor: "#f97316",
  },
  {
    id: "validation",
    label: "Validation",
    abbr: "VA",
    color: "#f59e0b",
    description: "LLM-powered. Generates assertion-based post-processing checks wrapped in try/except — checks for nulls, target column presence, row count sanity, infinite values, and class imbalance warnings.",
    badge: "LLM",
    badgeColor: "#f97316",
  },
  {
    id: "synthesizer",
    label: "Synthesizer",
    abbr: "SY",
    color: "#06b6d4",
    description: "Deterministic. Assembles all four specialist code snippets into a single executable Python script with a standard import block, a CSV load section, the four agent sections in order, and a save block.",
    badge: "No LLM",
    badgeColor: "#10b981",
  },
  {
    id: "executor",
    label: "Executor",
    abbr: "EX",
    color: "#ef4444",
    description: "Runs the synthesized script via subprocess. On failure, it feeds the error traceback back to the LLM and requests a corrected script. Retries up to 3 times before marking the run as failed.",
    badge: "LLM + subprocess",
    badgeColor: "#ef4444",
  },
];

export default function AgentFlow({ activeAgents = [] }) {
  const [hovered, setHovered] = useState(null);
  const active = new Set(activeAgents);
  const isActive = (id) => active.has(id);

  return (
    <div style={{ position: "relative", width: "100%" }}>

      {/* Tooltip slot — always occupies 130px so the diagram never shifts */}
      <div style={{ height: 130, position: "relative", marginBottom: 4 }}>
        {hovered && (
          <div style={{
            position: "absolute", top: 0, left: "50%", transform: "translateX(-50%)",
            width: "100%", maxWidth: 380,
            background: "rgba(13,13,43,0.98)",
            border: `1px solid ${hovered.color}55`,
            borderRadius: 12, padding: "14px 18px",
            zIndex: 50,
            boxShadow: `0 8px 40px ${hovered.color}33`,
            pointerEvents: "none",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span style={{
                width: 28, height: 28, borderRadius: 6, flexShrink: 0,
                background: `${hovered.color}22`, border: `1px solid ${hovered.color}55`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.72rem",
                color: hovered.color,
              }}>{hovered.abbr}</span>
              <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>{hovered.label} Agent</span>
              <span style={{
                marginLeft: "auto", padding: "2px 10px", borderRadius: 50,
                fontSize: "0.7rem", fontWeight: 600,
                background: `${hovered.badgeColor}22`,
                color: hovered.badgeColor,
                border: `1px solid ${hovered.badgeColor}44`,
                whiteSpace: "nowrap",
              }}>{hovered.badge}</span>
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.55, margin: 0 }}>
              {hovered.description}
            </p>
          </div>
        )}
      </div>

      {/* Flow diagram — layout is stable; tooltip slot absorbs all height changes */}
      <div>

        <FlowRow>
          <AgentNode agent={AGENTS[0]} isActive={isActive("profiler")} onHover={setHovered} />
        </FlowRow>
        <Arrow />
        <FlowRow>
          <AgentNode agent={AGENTS[1]} isActive={isActive("planner")} onHover={setHovered} />
        </FlowRow>
        <Arrow />
        <FlowRow>
          <AgentNode agent={AGENTS[2]} isActive={isActive("coordinator")} onHover={setHovered} wide />
        </FlowRow>

        {/* Coordinator bracket */}
        <div style={{ display: "flex", justifyContent: "center", margin: "4px 0" }}>
          <div style={{
            width: "70%", height: 24,
            borderLeft: "1px dashed rgba(255,255,255,0.15)",
            borderRight: "1px dashed rgba(255,255,255,0.15)",
            borderBottom: "1px dashed rgba(255,255,255,0.15)",
            borderRadius: "0 0 8px 8px",
          }} />
        </div>

        {/* Specialists row */}
        <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          {AGENTS.slice(3, 8).map((agent) => (
            <AgentNode key={agent.id} agent={agent} isActive={isActive(agent.id)} onHover={setHovered} small />
          ))}
        </div>

        <Arrow />
        <FlowRow>
          <AgentNode agent={AGENTS[8]} isActive={isActive("executor")} onHover={setHovered} />
        </FlowRow>
      </div>
    </div>
  );
}

function FlowRow({ children }) {
  return (
    <div style={{ display: "flex", justifyContent: "center", margin: "4px 0" }}>
      {children}
    </div>
  );
}

function Arrow() {
  return (
    <div style={{ display: "flex", justifyContent: "center", margin: "4px 0" }}>
      <svg width="12" height="20" viewBox="0 0 12 20" fill="none">
        <line x1="6" y1="0" x2="6" y2="14" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />
        <polyline points="2,10 6,16 10,10" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function AgentNode({ agent, isActive, onHover, wide, small }) {
  const width = small ? 110 : wide ? 260 : 200;
  const pad = small ? "10px 12px" : "14px 24px";

  return (
    <div
      onMouseEnter={() => onHover(agent)}
      onMouseLeave={() => onHover(null)}
      style={{
        width, padding: pad, borderRadius: 12, cursor: "pointer",
        border: `1px solid ${isActive ? agent.color : "rgba(255,255,255,0.1)"}`,
        background: isActive ? `${agent.color}18` : "rgba(255,255,255,0.03)",
        transition: "all 0.25s ease",
        textAlign: "center",
        boxShadow: isActive ? `0 0 20px ${agent.color}44` : "none",
        transform: isActive ? "scale(1.04)" : "scale(1)",
        animation: isActive ? "pulse-glow 2s infinite" : "none",
      }}
    >
      {/* Abbr badge */}
      <div style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: small ? 26 : 32, height: small ? 26 : 32,
        borderRadius: 6, marginBottom: 6,
        background: `${agent.color}20`, border: `1px solid ${agent.color}40`,
        fontFamily: "var(--font-mono)", fontWeight: 700,
        fontSize: small ? "0.65rem" : "0.75rem",
        color: agent.color,
      }}>{agent.abbr}</div>

      <div style={{
        fontWeight: 600,
        fontSize: small ? "0.72rem" : "0.88rem",
        color: isActive ? agent.color : "var(--text)",
      }}>
        {agent.label}
      </div>

      {!small && (
        <div style={{
          marginTop: 4, fontSize: "0.68rem", color: agent.badgeColor,
          fontFamily: "var(--font-mono)",
        }}>
          {agent.badge}
        </div>
      )}
    </div>
  );
}
