import { Link } from "react-router-dom";

const TECH_STACK = [
  { abbr: "LG", color: "#f97316", name: "LangGraph",    desc: "StateGraph orchestration" },
  { abbr: "CA", color: "#facc15", name: "Claude API",    desc: "Cloud LLM inference" },
  { abbr: "PD", color: "#fb923c", name: "pandas",        desc: "Data manipulation" },
  { abbr: "SK", color: "#f59e0b", name: "scikit-learn",  desc: "ML transforms" },
  { abbr: "FA", color: "#06b6d4", name: "FastAPI",       desc: "REST + SSE backend" },
  { abbr: "RE", color: "#ef4444", name: "React",         desc: "Interactive frontend" },
];

const DESIGN_DECISIONS = [
  {
    num: "01",
    title: "Shared State over Message Queues",
    body: "A single TypedDict MASState flows through all LangGraph nodes. Every agent reads from and writes to it — no Redis, no queues. LangGraph is designed around a single state object, and it makes the entire pipeline history inspectable in one place.",
  },
  {
    num: "02",
    title: "Coordinator Wraps Specialists",
    body: "The Cleaner, Outlier, Feature Engineer, Validation, and Synthesizer agents run inside the Coordinator rather than as separate LangGraph nodes. This ensures sequential data dependency — the cleaner's output underpins the outlier agent's assumptions.",
  },
  {
    num: "03",
    title: "Executor Separate from Synthesizer",
    body: "The Synthesizer assembles code; the Executor runs it. This separation enforces single-responsibility: the synthesizer can be tested without subprocess, and the executor's self-heal loop only needs the error traceback and the current file.",
  },
];

export default function Landing() {
  return (
    <main>
      {/* ── HERO ─────────────────────────────────────────────────────────── */}
      <section style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        position: "relative", overflow: "hidden", paddingTop: 80, paddingBottom: 96,
      }}>
        <div style={{
          position: "absolute", top: "20%", left: "10%",
          width: 500, height: 500, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(249,115,22,0.16) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", bottom: "10%", right: "5%",
          width: 400, height: 400, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(250,204,21,0.14) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />

        <div className="container" style={{ position: "relative", zIndex: 1 }}>
          <div style={{ maxWidth: 720, margin: "0 auto" }}>
            <div className="section-label fade-in-up">
              AAI · 8th Semester · FAST-NUCES Karachi
            </div>

            <h1 className="fade-in-up delay-1" style={{ fontSize: "clamp(2.2rem, 4vw, 3.4rem)", marginBottom: 20 }}>
              <span className="gradient-text">IntelliPrep MAS</span>
              <br />
              <span style={{ color: "var(--text)", fontWeight: 300 }}>
                Multi-Agent Preprocessing System
              </span>
            </h1>

            <p className="fade-in-up delay-2" style={{
              color: "var(--text-muted)", fontSize: "1.05rem", lineHeight: 1.8, marginBottom: 32,
            }}>
              A <strong style={{ color: "var(--text)" }}>9-agent hierarchical system</strong> that
              automatically profiles your CSV, plans preprocessing steps with an LLM, dispatches
              specialist agents for cleaning, outlier treatment, and feature engineering — then
              synthesizes and executes a complete Python script with a self-healing retry loop.
            </p>

            <div className="fade-in-up delay-3 landing-cta-row" style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <Link to="/try" className="btn btn-primary" style={{ fontSize: "1rem", padding: "14px 32px" }}>
                Try the Pipeline →
              </Link>
              <a href="https://github.com" className="btn btn-outline" style={{ fontSize: "1rem", padding: "14px 32px" }}>
                View Source
              </a>
            </div>

          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ─────────────────────────────────────────────────── */}
      <section className="section" style={{ background: "var(--bg-2)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <div className="section-label">How It Works</div>
            <h2 style={{ fontSize: "2.2rem" }}>
              Hierarchical <span className="gradient-text">MAS Pattern</span>
            </h2>
            <p style={{ color: "var(--text-muted)", maxWidth: 560, margin: "16px auto 0", fontSize: "1rem" }}>
              Three layers — Planner → Coordinator → Specialists — mirror the BDI
              (Beliefs, Desires, Intentions) agent architecture from multi-agent systems theory.
            </p>
          </div>

          <div className="landing-grid-3" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {[
              {
                step: "01", color: "#10b981",
                title: "Profile & Plan",
                body: "The deterministic Profiler analyses every column, infers the ML task type, and saves a compact JSON report. The LLM-powered Planner then reads the report and emits a structured preprocessing plan.",
              },
              {
                step: "02", color: "#f97316",
                title: "Coordinate & Generate",
                body: "The Coordinator dispatches the plan to four LLM specialist agents — Cleaner, Outlier, Feature Engineer, and Validation — each generating a Python code snippet assembled into a single executable script.",
              },
              {
                step: "03", color: "#ef4444",
                title: "Execute & Self-Heal",
                body: "The Executor runs the synthesized script via subprocess. On failure, it feeds the traceback back to the LLM and requests a corrected version, retrying up to 3 times before reporting an error.",
              },
            ].map(({ step, color, title, body }) => (
              <div key={step} className="glass" style={{
                borderRadius: 16, padding: 28,
                borderColor: `${color}22`,
                position: "relative", overflow: "hidden",
              }}>
                <div style={{
                  position: "absolute", top: 16, right: 16,
                  fontSize: "3rem", opacity: 0.05, fontWeight: 900,
                  fontFamily: "var(--font-mono)",
                }}>
                  {step}
                </div>
                <div style={{
                  width: 48, height: 48, borderRadius: 12, marginBottom: 16,
                  background: `${color}22`, border: `1px solid ${color}44`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: "1rem",
                  color,
                }}>{step}</div>
                <h3 style={{ fontSize: "1.05rem", marginBottom: 10 }}>{title}</h3>
                <p style={{ color: "var(--text-muted)", fontSize: "0.88rem", lineHeight: 1.7 }}>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── DESIGN DECISIONS ─────────────────────────────────────────────── */}
      <section className="section" style={{ background: "var(--bg-2)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <div className="section-label">Design</div>
            <h2 style={{ fontSize: "2.2rem" }}>
              Key <span className="gradient-text">Design Decisions</span>
            </h2>
          </div>
          <div className="landing-grid-3" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {DESIGN_DECISIONS.map(({ num, title, body }) => (
              <div key={num} className="glass" style={{ borderRadius: 16, padding: 28, position: "relative", overflow: "hidden" }}>
                <div style={{
                  position: "absolute", top: 16, right: 20,
                  fontFamily: "var(--font-mono)", fontSize: "3rem",
                  fontWeight: 900, opacity: 0.05,
                }}>{num}</div>
                <div style={{
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  width: 36, height: 36, borderRadius: 8, marginBottom: 14,
                  background: "rgba(249,115,22,0.16)", border: "1px solid rgba(249,115,22,0.35)",
                  fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.8rem",
                  color: "var(--primary-glow)",
                }}>{num}</div>
                <h3 style={{ fontSize: "1rem", marginBottom: 10 }}>{title}</h3>
                <p style={{ color: "var(--text-muted)", fontSize: "0.86rem", lineHeight: 1.75 }}>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TECH STACK ───────────────────────────────────────────────────── */}
      <section className="section">
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 48 }}>
            <div className="section-label">Stack</div>
            <h2 style={{ fontSize: "2.2rem" }}>Technology <span className="gradient-text">Stack</span></h2>
          </div>
          <div className="landing-stack-grid">
            {TECH_STACK.map(({ abbr, color, name, desc }) => (
              <div
                key={name}
                className="glass"
                style={{
                  borderRadius: 16,
                  padding: "20px 20px 18px",
                  position: "relative",
                  overflow: "hidden",
                  transition: "transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease",
                  border: "1px solid rgba(255,255,255,0.1)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-4px)";
                  e.currentTarget.style.boxShadow = "var(--shadow)";
                  e.currentTarget.style.borderColor = `${color}55`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow = "none";
                  e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)";
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: `radial-gradient(circle at 90% -10%, ${color}20 0%, transparent 42%)`,
                    pointerEvents: "none",
                  }}
                />
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 42,
                    height: 42,
                    borderRadius: 10,
                    marginBottom: 12,
                    background: `${color}20`,
                    border: `1px solid ${color}45`,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 800,
                    fontSize: "0.72rem",
                    color,
                  }}
                >
                  {abbr}
                </div>
                <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: 4 }}>{name}</div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.55 }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────────── */}
      <section className="section" style={{ textAlign: "center" }}>
        <div className="container" style={{ maxWidth: 600 }}>
          <div className="landing-cta-card" style={{
            padding: "56px 40px", borderRadius: 24,
            background: "linear-gradient(135deg, rgba(249,115,22,0.16), rgba(250,204,21,0.14))",
            border: "1px solid rgba(249,115,22,0.35)",
          }}>
            <div style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 56, height: 56, borderRadius: 14, marginBottom: 20,
              background: "linear-gradient(135deg, rgba(249,115,22,0.3), rgba(250,204,21,0.22))",
              border: "1px solid rgba(249,115,22,0.4)",
              fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: "1.1rem",
              color: "var(--primary-glow)",
            }}>MAS</div>
            <h2 style={{ fontSize: "2rem", marginBottom: 12 }}>
              Ready to <span className="gradient-text">preprocess</span>?
            </h2>
            <p style={{ color: "var(--text-muted)", marginBottom: 28, fontSize: "1rem" }}>
              Upload your CSV, choose your target column, and watch 9 agents
              collaborate in real time to prepare your data for ML.
            </p>
            <Link to="/try" className="btn btn-primary" style={{ fontSize: "1.05rem", padding: "14px 36px" }}>
              Launch the Pipeline →
            </Link>
          </div>
        </div>
      </section>

      <footer style={{
        borderTop: "1px solid var(--border)", padding: "24px 0",
        textAlign: "center", color: "var(--text-muted)", fontSize: "0.82rem",
      }}>
        <div className="container">
          IntelliPrep MAS · Agentic AI (AAI) · 8th Semester · FAST-NUCES Karachi
        </div>
      </footer>
    </main>
  );
}
