import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  SiAnthropic,
  SiFastapi,
  SiLangchain,
  SiPandas,
  SiReact,
  SiScikitlearn,
} from "react-icons/si";

const TECH_STACK = [
  {
    Icon: SiLangchain,
    brandColor: "#1C3C3C",
    name: "LangGraph",
    desc: "StateGraph orchestration",
  },
  {
    Icon: SiAnthropic,
    brandColor: "#191919",
    name: "Claude API",
    desc: "Cloud LLM inference",
  },
  {
    Icon: SiPandas,
    brandColor: "#150458",
    name: "pandas",
    desc: "Data manipulation",
  },
  {
    Icon: SiScikitlearn,
    brandColor: "#F89939",
    name: "scikit-learn",
    desc: "ML transforms",
  },
  {
    Icon: SiFastapi,
    brandColor: "#009688",
    name: "FastAPI",
    desc: "REST + SSE backend",
  },
  {
    Icon: SiReact,
    brandColor: "#149ECA",
    name: "React",
    desc: "Interactive frontend",
  },
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
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (pathname !== "/") return;
    if (!hash) return;
    const id = hash.replace(/^#/, "");
    const el = document.getElementById(id);
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [pathname, hash]);

  return (
    <main>
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section
        id="hero"
        className="mesh-orbs"
        style={{
          minHeight: "100vh", display: "flex", alignItems: "center",
          position: "relative", overflow: "hidden", paddingTop: 80, paddingBottom: 96,
          background: "linear-gradient(168deg, rgba(255,255,255,0.72) 0%, rgba(255,237,213,0.35) 38%, rgba(255,251,235,0.2) 72%, rgba(254,215,170,0.12) 100%)",
        }}
      >
        <div className="container" style={{ position: "relative", zIndex: 1 }}>
          <div style={{ maxWidth: 720, margin: "0 auto" }}>
            <h1 className="fade-in-up" style={{ fontSize: "clamp(2.2rem, 4vw, 3.4rem)", marginBottom: 20 }}>
              <span className="gradient-text">IntelliPrep MAS</span>
              <br />
              <span style={{ color: "var(--text)", fontWeight: 300 }}>
                Multi-Agent Preprocessing System
              </span>
            </h1>

            <p className="fade-in-up delay-1" style={{
              color: "var(--text-muted)", fontSize: "1.05rem", lineHeight: 1.75, marginBottom: 28,
            }}>
              Agentic AI that turns raw CSVs into clean, model-ready data — with full transparency
              over every preprocessing decision.
            </p>

            <div className="fade-in-up delay-2 landing-cta-row" style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <Link to="/try" className="btn btn-primary" style={{ fontSize: "1rem", padding: "14px 32px" }}>
                Try the Pipeline →
              </Link>
              <Link to="/#about" className="btn btn-outline" style={{ fontSize: "1rem", padding: "14px 32px" }}>
                Learn more
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── About ─────────────────────────────────────────────────────────── */}
      <section id="about" className="section" style={{ background: "var(--section-light)" }}>
        <div className="container">
          <div style={{ maxWidth: 760, margin: "0 auto", textAlign: "center" }}>
            <div className="section-label">About</div>
            <h2 style={{ fontSize: "2.2rem", marginBottom: 20 }}>
              What is <span className="gradient-text">IntelliPrep</span>?
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: "1.05rem", lineHeight: 1.85, marginBottom: 16 }}>
              A <strong style={{ color: "var(--text)" }}>9-agent hierarchical system</strong> that
              automatically profiles your CSV, plans preprocessing steps with an LLM, dispatches
              specialist agents for cleaning, outlier treatment, and feature engineering — then
              synthesizes and executes a complete Python script with a self-healing retry loop.
            </p>
            <p style={{ color: "var(--text-muted)", fontSize: "1rem", lineHeight: 1.8 }}>
              Built for Agentic AI coursework at FAST-NUCES: LangGraph orchestration, shared typed state,
              and a FastAPI + React demo so you can watch the pipeline run end-to-end on your own data.
            </p>
          </div>
        </div>
      </section>

      {/* ── Workflow ───────────────────────────────────────────────────────── */}
      <section id="workflow" className="section" style={{ background: "var(--section-warm)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <div className="section-label">Workflow</div>
            <h2 style={{ fontSize: "2.2rem" }}>
              Hierarchical <span className="gradient-text">MAS pattern</span>
            </h2>
            <p style={{ color: "var(--text-muted)", maxWidth: 560, margin: "16px auto 0", fontSize: "1rem" }}>
              Three layers — Planner → Coordinator → Specialists — mirror the BDI
              (Beliefs, Desires, Intentions) agent architecture from multi-agent systems theory.
            </p>
          </div>

          <div className="landing-grid-3" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {[
              {
                step: "01", color: "#059669",
                title: "Profile & Plan",
                body: "The deterministic Profiler analyses every column, infers the ML task type, and saves a compact JSON report. The LLM-powered Planner then reads the report and emits a structured preprocessing plan.",
              },
              {
                step: "02", color: "#ea6c00",
                title: "Coordinate & Generate",
                body: "The Coordinator dispatches the plan to four LLM specialist agents — Cleaner, Outlier, Feature Engineer, and Validation — each generating a Python code snippet assembled into a single executable script.",
              },
              {
                step: "03", color: "#dc2626",
                title: "Execute & Self-Heal",
                body: "The Executor runs the synthesized script via subprocess. On failure, it feeds the traceback back to the LLM and requests a corrected version, retrying up to 3 times before reporting an error.",
              },
            ].map(({ step, color, title, body }) => (
              <div key={step} className="glass" style={{
                borderRadius: 16, padding: 28,
                borderColor: `${color}28`,
                position: "relative", overflow: "hidden",
              }}>
                <div style={{
                  position: "absolute", top: 16, right: 16,
                  fontSize: "3rem", opacity: 0.04, fontWeight: 900,
                  fontFamily: "var(--font-mono)", color: color,
                }}>
                  {step}
                </div>
                <div style={{
                  width: 48, height: 48, borderRadius: 12, marginBottom: 16,
                  background: `${color}14`, border: `1px solid ${color}30`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: "1rem",
                  color,
                }}>{step}</div>
                <h3 style={{ fontSize: "1.05rem", marginBottom: 10, color: "var(--text)" }}>{title}</h3>
                <p style={{ color: "var(--text-muted)", fontSize: "0.88rem", lineHeight: 1.7 }}>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Design ───────────────────────────────────────────────────────── */}
      <section id="design" className="section" style={{ background: "var(--section-light)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <div className="section-label">Design</div>
            <h2 style={{ fontSize: "2.2rem" }}>
              Key <span className="gradient-text">design decisions</span>
            </h2>
          </div>
          <div className="landing-grid-3" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {DESIGN_DECISIONS.map(({ num, title, body }) => (
              <div key={num} className="glass" style={{ borderRadius: 16, padding: 28, position: "relative", overflow: "hidden" }}>
                <div style={{
                  position: "absolute", top: 16, right: 20,
                  fontFamily: "var(--font-mono)", fontSize: "3rem",
                  fontWeight: 900, opacity: 0.04, color: "var(--primary)",
                }}>{num}</div>
                <div style={{
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  width: 36, height: 36, borderRadius: 8, marginBottom: 14,
                  background: "rgba(234,108,0,0.10)", border: "1px solid rgba(234,108,0,0.25)",
                  fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.8rem",
                  color: "var(--primary)",
                }}>{num}</div>
                <h3 style={{ fontSize: "1rem", marginBottom: 10, color: "var(--text)" }}>{title}</h3>
                <p style={{ color: "var(--text-muted)", fontSize: "0.86rem", lineHeight: 1.75 }}>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Stack ─────────────────────────────────────────────────────────── */}
      <section id="stack" className="section" style={{ background: "var(--section-warm)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: 48 }}>
            <div className="section-label">Stack</div>
            <h2 style={{ fontSize: "2.2rem" }}>Technology <span className="gradient-text">stack</span></h2>
          </div>
          <div className="landing-stack-grid">
            {TECH_STACK.map(({ Icon, brandColor, name, desc }) => (
              <div
                key={name}
                className="glass"
                style={{
                  borderRadius: 16,
                  padding: "20px 20px 18px",
                  position: "relative",
                  overflow: "hidden",
                  transition: "transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-4px)";
                  e.currentTarget.style.boxShadow = "0 8px 28px rgba(234,108,0,0.18)";
                  e.currentTarget.style.borderColor = `${brandColor}55`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow = "0 1px 8px rgba(180,80,0,0.08)";
                  e.currentTarget.style.borderColor = "rgba(180,80,0,0.13)";
                }}
              >
                <div style={{
                  position: "absolute", inset: 0,
                  background: `radial-gradient(circle at 90% -10%, ${brandColor}18 0%, transparent 42%)`,
                  pointerEvents: "none",
                }} />
                <div
                  role="img"
                  aria-label={`${name} logo`}
                  style={{
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  width: 48, height: 48, borderRadius: 12, marginBottom: 12,
                  background: `${brandColor}12`, border: `1px solid ${brandColor}28`,
                  color: brandColor,
                }}
                >
                  <Icon size={28} aria-hidden />
                </div>
                <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: 4, color: "var(--text)" }}>{name}</div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.55 }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Get started (CTA) ─────────────────────────────────────────────── */}
      <section id="cta" className="section" style={{ textAlign: "center", background: "var(--section-cta)" }}>
        <div className="container" style={{ maxWidth: 600 }}>
          <div className="landing-cta-card" style={{
            padding: "56px 40px", borderRadius: 24,
            background: "linear-gradient(145deg, rgba(255,255,255,0.92) 0%, rgba(255,237,213,0.55) 38%, rgba(254,215,170,0.35) 100%)",
            border: "1px solid rgba(234,108,0,0.28)",
            boxShadow: "0 12px 40px rgba(234,108,0,0.12), 0 1px 0 rgba(255,255,255,0.9) inset",
          }}>
            <div style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 56, height: 56, borderRadius: 14, marginBottom: 20,
              background: "linear-gradient(135deg, rgba(234,108,0,0.18), rgba(217,119,6,0.14))",
              border: "1px solid rgba(234,108,0,0.30)",
              fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: "1.1rem",
              color: "var(--primary)",
            }}>MAS</div>
            <h2 style={{ fontSize: "2rem", marginBottom: 12, color: "var(--text)" }}>
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

      <footer id="team" style={{
        borderTop: "1px solid rgba(234,108,0,0.14)", padding: "28px 0",
        textAlign: "center", color: "var(--text-muted)", fontSize: "0.82rem",
        background: "linear-gradient(180deg, rgba(255,251,235,0.95) 0%, rgba(255,228,200,0.9) 100%)",
      }}>
        <div className="container" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ color: "var(--text)", fontWeight: 600 }}>
            Team
          </div>
          <div style={{
            display: "flex", flexDirection: "column", gap: 6,
            fontSize: "0.86rem", lineHeight: 1.55,
          }}>
            <span>Ahmed Raza <span style={{ color: "var(--primary)", fontFamily: "var(--font-mono)" }}>[22K-4422]</span></span>
            <span>Fatimah Ansari <span style={{ color: "var(--primary)", fontFamily: "var(--font-mono)" }}>[22K-4538]</span></span>
            <span>Arisha Rehan Chotani <span style={{ color: "var(--primary)", fontFamily: "var(--font-mono)" }}>[22K-4569]</span></span>
          </div>
          <div style={{ paddingTop: 8, borderTop: "1px solid var(--border)", fontSize: "0.8rem", opacity: 0.9 }}>
            IntelliPrep MAS · Agentic AI (AAI) · 8th Semester · FAST-NUCES Karachi
          </div>
        </div>
      </footer>
    </main>
  );
}
