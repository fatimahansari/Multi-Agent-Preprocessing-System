# IntelliPrep MAS: Multi-Agent Preprocessing System

**Course:** Agentic AI (AAI) — 8th Semester, FAST-NUCES Karachi

---

## Background

IntelliPrep began as a monolithic preprocessing agent: a single Python class that
profiled a CSV, inferred the ML task type, decided on cleaning and feature-engineering
strategies, generated code, and executed it — all inside one tightly-coupled workflow.
While functional, the monolith was fragile: any change to outlier logic touched the
same file as datetime parsing, LLM prompts were mixed with deterministic pandas code,
and the self-healing executor had no clean way to retry individual stages.
Converting the system to a **Multi-Agent System (MAS)** decouples each concern into a
dedicated agent with a single responsibility, allows the LangGraph orchestrator to
compose them as nodes in a directed graph, and makes the pipeline fault-tolerant — a
failure in one specialist agent appends to `state["errors"]` and the rest of the
pipeline continues rather than crashing entirely.

---

## MAS Architecture

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        LangGraph StateGraph                             │
  │                                                                         │
  │   ┌──────────┐    ┌──────────┐    ┌─────────────────────────────────┐  │
  │   │ Profiler │───▶│ Planner  │───▶│           Coordinator           │  │
  │   │  Agent   │    │  Agent   │    │                                 │  │
  │   │          │    │  (LLM)   │    │  ┌─────────┐  ┌─────────────┐  │  │
  │   │ (determ.)│    └──────────┘    │  │ Cleaner │  │   Outlier   │  │  │
  │   └──────────┘                   │  │  Agent  │─▶│    Agent    │  │  │
  │                                  │  │  (LLM)  │  │    (LLM)    │  │  │
  │                                  │  └─────────┘  └──────┬──────┘  │  │
  │                                  │                       │         │  │
  │                                  │  ┌────────────────────▼──────┐  │  │
  │                                  │  │   FeatureEngineer Agent   │  │  │
  │                                  │  │          (LLM)            │  │  │
  │                                  │  └────────────────────┬──────┘  │  │
  │                                  │                       │         │  │
  │                                  │  ┌────────────────────▼──────┐  │  │
  │                                  │  │    Validation Agent       │  │  │
  │                                  │  │          (LLM)            │  │  │
  │                                  │  └────────────────────┬──────┘  │  │
  │                                  │                       │         │  │
  │                                  │  ┌────────────────────▼──────┐  │  │
  │                                  │  │  CodeSynthesizer Agent    │  │  │
  │                                  │  │       (deterministic)     │  │  │
  │                                  │  └───────────────────────────┘  │  │
  │                                  └──────────────┬──────────────────┘  │
  │                                                 │                      │
  │                                   ┌─────────────▼──────────┐          │
  │                                   │     Executor Agent     │          │
  │                                   │  (subprocess + LLM     │          │
  │                                   │   self-heal loop)      │          │
  │                                   └─────────────┬──────────┘          │
  │                                                 │                      │
  │                                               [END]                    │
  └─────────────────────────────────────────────────────────────────────────┘
```

| Agent | Role |
|---|---|
| **ProfilerAgent** | Deterministic. Loads CSV, computes per-column statistics (dtype, nulls, skewness, top values), infers ML task type (regression / classification / forecasting), saves `_report.json`. |
| **PlannerAgent** | LLM-powered. Reads the report JSON and emits a structured plan JSON with four sections: `cleaning_steps`, `outlier_steps`, `feature_steps`, `validation_steps`. |
| **CoordinatorAgent** | No LLM. Dispatches the plan to the four specialist agents in sequence, collects their code snippets, tolerates per-agent errors without stopping the pipeline. |
| **CleanerAgent** | LLM-powered. Generates pandas code for duplicate removal, missing-value imputation, ID/datetime column handling, and free-text column removal. |
| **OutlierAgent** | LLM-powered. Generates per-column outlier treatment code (IQR clip/remove/flag, Z-score, IsolationForest). |
| **FeatureEngineerAgent** | LLM-powered. Generates encoding (OHE, label, target), scaling (MinMax, Standard), log transforms, and cyclical encodings. |
| **ValidationAgent** | LLM-powered. Generates assertion-based post-processing checks wrapped in `try/except` so warnings print but execution continues. |
| **CodeSynthesizerAgent** | Deterministic. Assembles all snippets into a single executable `.py` file with standard imports, a load block, and a save block. |
| **ExecutorAgent** | Runs the synthesized script via `subprocess`. On failure, calls the LLM with the error traceback for a corrected script, then retries (up to 3 times). |

---

## How Agents Communicate

All agents share a single `MASState` dictionary — a `TypedDict` defined in
`core/shared_state.py` — that acts as the **message bus** for the entire pipeline.

```
  ┌─────────────────────────────────────────────────────┐
  │                      MASState                       │
  │                                                     │
  │  dataset_path ──────────────────▶ ProfilerAgent     │
  │  target_column                                      │
  │                                                     │
  │  report       ◀──── ProfilerAgent                  │
  │               ─────────────────▶ PlannerAgent       │
  │                                                     │
  │  plan         ◀──── PlannerAgent                   │
  │               ─────────────────▶ CoordinatorAgent   │
  │                                  (reads each section│
  │                                   for its agents)   │
  │                                                     │
  │  agent_outputs◀──── Cleaner / Outlier / FE /       │
  │                      Validation agents              │
  │               ─────────────────▶ CodeSynthesizer    │
  │                                                     │
  │  synthesized_ ◀──── CodeSynthesizer                │
  │  code / script                                      │
  │               ─────────────────▶ ExecutorAgent      │
  │                                                     │
  │  execution_log, errors, status, retry_count         │
  │  file_history  ◀──── updated by every agent        │
  └─────────────────────────────────────────────────────┘
```

Each agent receives the full state dict, mutates only its own fields, and returns
the updated dict.  The **CoordinatorAgent** is the one exception: rather than writing
a single artefact it explicitly calls `agent.run(state)` on each specialist in order,
passing state through the chain so that each specialist's output is available to the
next (e.g. the cleaner's output is visible to the outlier agent through the log).

---

## Technology Stack

| Component | Technology |
|---|---|
| Orchestration graph | [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` |
| LLM backend | [Ollama](https://ollama.com/) — local inference, no API key required |
| Default model | `qwen2.5-coder:7b` (configurable via env var) |
| Data manipulation | pandas, NumPy |
| ML transforms | scikit-learn (`LabelEncoder`, `MinMaxScaler`, `StandardScaler`, `IsolationForest`) |
| HTTP (LLM calls) | Python stdlib `urllib.request` — zero extra dependencies |
| CLI | Python stdlib `argparse` |
| Testing | pytest + `unittest.mock` |

---

## Setup

### 1. Install Python dependencies

```bash
pip install langgraph langchain-core pandas scikit-learn
```

### 2. Pull the LLM model via Ollama

```bash
# Install Ollama from https://ollama.com/download, then:
ollama pull qwen2.5-coder:7b
```

### 3. (Optional) Override model or endpoint via environment variables

```bash
export OLLAMA_MODEL="llama3"
export OLLAMA_ENDPOINT="http://192.168.1.10:11434"
```

---

## Usage

```bash
# Basic usage
python main.py --csv path/to/data.csv --target column_name

# Save the final MAS state to JSON (alongside the CSV)
python main.py --csv path/to/data.csv --target price --save-state

# Use a different model / remote Ollama instance
python main.py --csv data.csv --target label \
    --model llama3 \
    --endpoint http://192.168.1.10:11434
```

**Output files** (written next to the input CSV):

| File | Contents |
|---|---|
| `{stem}_report.json` | Profiler dataset statistics |
| `{stem}_plan.json` | LLM-generated preprocessing plan |
| `{stem}_preprocessing.py` | Synthesized, executable Python script |
| `{stem}_preprocessed.csv` | Final cleaned and engineered dataset |
| `{stem}_mas_state.json` | Full pipeline state (with `--save-state`) |

### Running the smoke test

```bash
cd aai_mas_preprocessing
pytest tests/test_smoke.py -v
```

---

## Agent Communication Pattern

This system implements a **Hierarchical MAS** pattern:

```
  LangGraph graph (top-level sequencing)
       │
       ├── ProfilerAgent    (Layer 1 — perception)
       ├── PlannerAgent     (Layer 2 — deliberation / LLM reasoning)
       ├── CoordinatorAgent (Layer 3 — task decomposition & dispatch)
       │       ├── CleanerAgent          (Layer 4 — specialist execution)
       │       ├── OutlierAgent
       │       ├── FeatureEngineerAgent
       │       ├── ValidationAgent
       │       └── CodeSynthesizerAgent
       └── ExecutorAgent    (Layer 5 — action + self-healing)
```

The three-tier hierarchy (Planner → Coordinator → Specialists) mirrors classical
BDI agent architectures: the **Planner** handles *beliefs* (what the data looks like)
and *desires* (what preprocessing is needed); the **Coordinator** manages *intentions*
(which agent executes which step); and the **Specialists** are reactive agents that
carry out atomic tasks.

---

## Key Design Decisions

### Shared state over message-passing queues

A `TypedDict` shared-state dictionary was chosen over an explicit message-passing
queue (e.g. Redis, RabbitMQ, or an in-process `queue.Queue`) for two reasons:

1. **LangGraph compatibility** — LangGraph's `StateGraph` is designed around a single
   state object that flows through nodes. Wrapping a queue inside this model would
   add complexity without benefit.
2. **Simplicity and debuggability** — at any point during or after the run, the entire
   pipeline's history (logs, errors, artefact paths, generated code) is readable in one
   place. There is no need to reconstruct what happened by joining messages from multiple
   queues.

The trade-off accepted is that agents are not independently deployable as microservices;
for a research/semester-project context this is acceptable.

### Coordinator wraps specialists (not separate graph nodes)

The five specialist agents (Cleaner, Outlier, FeatureEngineer, Validation, Synthesizer)
run *inside* the Coordinator rather than as separate LangGraph nodes.  This is
intentional: each specialist's output must be available to the next as *input data*
(the cleaner's null-free DataFrame underpins the outlier agent's assumptions), so they
must run sequentially with shared state passed through directly.  Flattening them into
the graph would require conditional edges and checkpoint logic to handle partial
failures, making the graph topology more complex without improving fault tolerance.

### Executor is separate from Synthesizer (generation ≠ execution)

The **CodeSynthesizerAgent** assembles snippets into a script but never runs it.
The **ExecutorAgent** runs the script but does not generate code from scratch — it
only fixes it on failure.  This separation enforces the *single-responsibility
principle*:

- The synthesizer can be tested in isolation by checking the script's text without
  running a subprocess.
- The executor's self-heal loop always works on a complete, on-disk script — it never
  needs to understand the original agent outputs, only the current error and the
  current file.
- Replacing the executor (e.g. switching from `subprocess` to a sandboxed Docker
  container) requires no changes to the synthesizer or any upstream agent.
