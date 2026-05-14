import { useState, useRef, useCallback } from "react";
import ProgressPanel from "../components/ProgressPanel.jsx";

const API = "";
const STEPS = ["Upload CSV", "Configure", "Run Pipeline"];

export default function TryNow() {
  const [step, setStep] = useState(0);

  const [file, setFile] = useState(null);
  const [csvPath, setCsvPath] = useState("");
  const [columns, setColumns] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  const [targetCol, setTargetCol] = useState("");

  const [runId, setRunId] = useState(null);
  const [events, setEvents] = useState([]);
  const [runStatus, setRunStatus] = useState("idle");
  const [finalState, setFinalState] = useState(null);
  const [runError, setRunError] = useState("");
  const esRef = useRef(null);
  const planFromSseRef = useRef(null);

  const handleFileDrop = useCallback((e) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer?.files?.[0] || e.target.files?.[0];
    if (f) handleFileSelect(f);
  }, []);

  const handleFileSelect = (f) => {
    if (!f.name.endsWith(".csv")) { setUploadError("Please select a .csv file."); return; }
    setFile(f); setUploadError("");
  };

  const doUpload = async () => {
    if (!file) return;
    setUploading(true); setUploadError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setCsvPath(data.csv_path);
      setColumns(data.columns || []);
      if (data.columns?.length > 0) setTargetCol(data.columns[data.columns.length - 1]);
      setStep(1);
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const doRun = async () => {
    if (!targetCol) return;
    setRunStatus("running"); setEvents([]); setFinalState(null);
    setRunError(""); setStep(2);

    let rid;
    try {
      const res = await fetch(`${API}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          csv_path: csvPath, target_column: targetCol,
        }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      rid = data.run_id;
      setRunId(rid);
    } catch (err) {
      setRunStatus("error"); setRunError(err.message); return;
    }

    if (esRef.current) esRef.current.close();
    const es = new EventSource(`${API}/api/progress/${rid}`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        if (evt.type === "plan") {
          try { planFromSseRef.current = JSON.parse(evt.message); } catch { /* ignore */ }
        } else if (evt.type === "done") {
          setRunStatus(evt.status === "done" ? "done" : "error");
          es.close();
          fetch(`${API}/api/result/${rid}`)
            .then((r) => {
              if (!r.ok) throw new Error(`HTTP ${r.status}`);
              return r.json();
            })
            .then((r) => { if (r.final_state) setFinalState(r.final_state); })
            .catch(() => {
              // /api/result unavailable (e.g. server reloaded) — synthesize a
              // minimal finalState from what the SSE plan event already gave us.
              setFinalState((prev) => prev ?? { plan: planFromSseRef.current, errors: [], status: evt.status });
            });
        } else {
          setEvents((prev) => [...prev, evt]);
        }
      } catch { /* ignore */ }
    };

    es.onerror = () => {
      setRunStatus((s) => s === "running" ? "error" : s);
      setRunError("Lost connection to server.");
      es.close();
    };
  };

  const reset = () => {
    if (esRef.current) esRef.current.close();
    planFromSseRef.current = null;
    setStep(0); setFile(null); setCsvPath(""); setColumns([]);
    setTargetCol(""); setEvents([]); setRunStatus("idle");
    setFinalState(null); setRunError(""); setRunId(null);
  };

  return (
    <main style={{ paddingTop: 80, minHeight: "100vh", background: "transparent" }}>
      <div className="container" style={{ paddingTop: 40, paddingBottom: 80 }}>

        {/* Page header */}
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div className="section-label">Interactive Demo</div>
          <h1 style={{ fontSize: "2.4rem", marginBottom: 12 }}>
            <span className="gradient-text">Run the Pipeline</span>
          </h1>
          <p style={{ color: "var(--text-muted)", maxWidth: 520, margin: "0 auto", fontSize: "1rem" }}>
            Upload a CSV, choose your target column, and watch 9 agents
            collaborate in real time to preprocess your dataset.
          </p>
        </div>

        {/* Step indicator */}
        <div className="step-indicator-wrap" style={{ display: "flex", justifyContent: "center", marginBottom: 48 }}>
          {STEPS.map((label, i) => (
            <div key={i} className="step-item" style={{ display: "flex", alignItems: "center" }}>
              <div style={{
                display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
                opacity: i > step ? 0.4 : 1, transition: "opacity 0.3s",
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: "50%",
                  border: `2px solid ${i === step ? "var(--primary)" : i < step ? "var(--accent)" : "rgba(255,255,255,0.15)"}`,
                  background: i < step ? "var(--accent)" : i === step ? "rgba(249,115,22,0.22)" : "transparent",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 700, fontSize: "0.85rem",
                  fontFamily: "var(--font-mono)",
                  color: i < step ? "#000" : i === step ? "var(--primary-glow)" : "var(--text-muted)",
                  transition: "all 0.4s ease",
                }}>
                  {i < step ? "✓" : i + 1}
                </div>
                <span style={{
                  fontSize: "0.75rem",
                  color: i === step ? "var(--primary-glow)" : "var(--text-muted)",
                  fontWeight: i === step ? 600 : 400,
                }}>
                  {label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className="step-divider" style={{
                  width: 80, height: 2, margin: "0 8px", marginBottom: 22,
                  background: i < step ? "var(--accent)" : "rgba(255,255,255,0.08)",
                  transition: "background 0.4s",
                }} />
              )}
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 32, alignItems: "start" }}>

          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

            {/* Step 0: Upload */}
            {step === 0 && (
              <Panel title="Upload your CSV dataset">
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleFileDrop}
                  onClick={() => fileRef.current?.click()}
                  style={{
                    border: `2px dashed ${dragOver ? "var(--primary)" : file ? "var(--accent)" : "rgba(180,80,0,0.18)"}`,
                    borderRadius: 14, padding: "48px 24px", textAlign: "center",
                    cursor: "pointer", transition: "all 0.2s ease",
                    background: dragOver ? "rgba(234,108,0,0.07)" : file ? "rgba(217,119,6,0.07)" : "rgba(249,115,22,0.02)",
                  }}
                >
                  <input ref={fileRef} type="file" accept=".csv" style={{ display: "none" }}
                    onChange={(e) => handleFileSelect(e.target.files[0])} />

                  {/* SVG icon */}
                  <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
                    {file ? (
                      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                        <circle cx="20" cy="20" r="19" stroke="var(--primary)" strokeWidth="1.5" />
                        <polyline points="12,21 18,27 29,14" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    ) : (
                      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                        <rect x="8" y="4" width="18" height="24" rx="3" stroke="rgba(180,80,0,0.35)" strokeWidth="1.5" />
                        <path d="M26 4 L34 12 L26 12 Z" stroke="rgba(180,80,0,0.35)" strokeWidth="1.5" strokeLinejoin="round" />
                        <line x1="13" y1="16" x2="23" y2="16" stroke="rgba(180,80,0,0.25)" strokeWidth="1.5" />
                        <line x1="13" y1="20" x2="21" y2="20" stroke="rgba(180,80,0,0.25)" strokeWidth="1.5" />
                        <circle cx="30" cy="30" r="8" fill="rgba(234,108,0,0.14)" stroke="var(--primary)" strokeWidth="1.5" />
                        <line x1="30" y1="26" x2="30" y2="34" stroke="var(--primary)" strokeWidth="1.5" strokeLinecap="round" />
                        <line x1="26" y1="30" x2="34" y2="30" stroke="var(--primary)" strokeWidth="1.5" strokeLinecap="round" />
                      </svg>
                    )}
                  </div>

                  {file ? (
                    <>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>{file.name}</div>
                      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                        {(file.size / 1024).toFixed(1)} KB · Click to change
                      </div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>Drop CSV here or click to browse</div>
                      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Supports any .csv file</div>
                    </>
                  )}
                </div>

                {uploadError && (
                  <div style={{ color: "var(--danger)", fontSize: "0.85rem", marginTop: 4 }}>
                    {uploadError}
                  </div>
                )}

                <button className="btn btn-primary"
                  style={{ width: "100%", justifyContent: "center", padding: "14px" }}
                  disabled={!file || uploading} onClick={doUpload}>
                  {uploading ? <Spinner /> : "Upload and Continue →"}
                </button>
              </Panel>
            )}

            {/* Step 1: Configure */}
            {step === 1 && (
              <Panel title="Configure the pipeline">
                <FormField label="Target column" required>
                  {columns.length > 0 ? (
                    <select value={targetCol} onChange={(e) => setTargetCol(e.target.value)} style={selectStyle}>
                      {columns.map((c) => (
                        <option
                          key={c}
                          value={c}
                          style={{ backgroundColor: "#fff", color: "#1c0f00" }}
                        >
                          {c}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input type="text" value={targetCol}
                      onChange={(e) => setTargetCol(e.target.value)}
                      placeholder="e.g. price, label, target"
                      style={inputStyle} />
                  )}
                </FormField>

                <div className="pipeline-action-row" style={{ display: "flex", gap: 10, marginTop: 4 }}>
                  <button className="btn btn-outline" style={{ flex: 1, justifyContent: "center" }} onClick={() => setStep(0)}>
                    Back
                  </button>
                  <button className="btn btn-primary"
                    style={{ flex: 2, justifyContent: "center", padding: "14px" }}
                    disabled={!targetCol} onClick={doRun}>
                    Run Pipeline →
                  </button>
                </div>
              </Panel>
            )}

            {/* Step 2: Running */}
            {step === 2 && (
              <>
                <ProgressPanel events={events} status={runStatus} finalState={finalState} runId={runId} />

                {runError && (
                  <div style={{
                    padding: "14px 18px", borderRadius: 10,
                    background: "rgba(220,38,38,0.06)",
                    border: "1px solid rgba(220,38,38,0.20)",
                    color: "var(--danger)", fontSize: "0.87rem",
                  }}>
                    {runError}
                  </div>
                )}

                {(runStatus === "done" || runStatus === "error") && (
                  <button className="btn btn-outline" style={{ justifyContent: "center" }} onClick={reset}>
                    Run Another Dataset
                  </button>
                )}
              </>
            )}
          </div>

        </div>
      </div>
    </main>
  );
}

function Panel({ title, children }) {
  return (
    <div className="glass pipeline-panel" style={{ borderRadius: 16, padding: 28 }}>
      <h2 style={{ fontSize: "1.1rem", marginBottom: 20, fontWeight: 600 }}>{title}</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>{children}</div>
    </div>
  );
}

function FormField({ label, required, children }) {
  return (
    <div>
      <label style={{
        display: "block", fontSize: "0.82rem",
        color: "var(--text-muted)", marginBottom: 6, fontWeight: 500,
      }}>
        {label}{required && <span style={{ color: "var(--danger)" }}> *</span>}
      </label>
      {children}
    </div>
  );
}

function Spinner() {
  return (
    <span style={{
      width: 16, height: 16, borderRadius: "50%",
      border: "2px solid rgba(255,255,255,0.3)",
      borderTopColor: "#fff", display: "inline-block",
      animation: "spin 0.7s linear infinite",
    }} />
  );
}

const inputStyle = {
  width: "100%", padding: "10px 14px", borderRadius: 8,
  background: "#fff",
  border: "1px solid rgba(180,80,0,0.18)",
  color: "var(--text)", fontFamily: "var(--font-mono)", fontSize: "0.88rem",
  outline: "none", transition: "border-color 0.2s",
};

const selectStyle = {
  ...inputStyle,
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
  backgroundColor: "#fff",
  color: "var(--text)",
};
