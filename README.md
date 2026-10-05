# GlobalTech HR Multi-Agent Automation System (LangGraph & MCP)

[![CI/CD Pipeline](https://github.com/your-org/msaie-agentic-HR/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/msaie-agentic-HR/actions)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%20%7C%203.14-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph%20v1.2-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![MCP](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-orange.svg)](https://modelcontextprotocol.io/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)

An autonomous, multi-agent Human Resources automation system built with **LangGraph** and the **Model Context Protocol (MCP)**. The system handles **new hire onboarding**, **HR policy Q&A (RAG with precise citations)**, and **employee self-service tool execution** with explicit action safety guardrails.

> [!NOTE]
> **Live Deployment & Cold-Start Notice:** The live application is hosted at [https://msaie-agentic-hr.onrender.com](https://msaie-agentic-hr.onrender.com). This application is deployed on a free instance of Render and spins down during inactivity, which can delay initial requests by 50 seconds or more while the container spins back up.

---

## 📚 Project Documentation Index

- **[design-and-evaluation.md](design-and-evaluation.md)**: Comprehensive architectural justification, RAG design, MCP server transport, LangGraph agent orchestration, 8 tool schemas, action-safety guardrails, deployment choices, all 25 benchmark evaluation questions, expected answers, and evaluation results.
- **[ai-tooling.md](ai-tooling.md)**: Detailed retrospective on AI coding tools utilized (Antigravity IDE / Gemini, AppTest, pytest), what worked well, failure modes encountered (Streamlit re-import caching, package manager constraints), and resolutions.
- **[deployed.md](deployed.md)**: Live deployment endpoints, `/health` and `/chat` specifications, and free-tier container cold-start behavior notes.

---

## 🌟 Key Capabilities

1. **Multi-Agent Orchestration (LangGraph):**
   - **LLM Intent Router:** Utilizes the LLM to semantically classify user requests into specialized workflows (`policy_rag`, `onboarding`, `employee_workflow`, `clarification`, `out_of_scope`) with entity extraction and routing rationale.
   - **Scope Guardrails:** Detects and politely refuses queries outside the HR domain.
   - **Ambiguity Handler:** Prompts for clarification when critical parameters (e.g., employee ID, leave dates) are missing.
   - **Policy RAG Agent:** Semantic retrieval across multi-format policies with source citations, snippets, and factual grounding.
   - **Onboarding Agent:** Inspects checklist progress, verifies equipment eligibility, and drafts welcome roadmaps.
   - **Employee Tool Agent:** Checks live PTO balances, validates notice compliance, and files mock tickets.

2. **Model Context Protocol (MCP) Integration:**
   - 8 fully registered MCP tools built using **FastMCP** (`mcp.server.fastmcp`) with `@mcp.tool()` decorators.
   - Client connectivity and LangChain tool conversion powered by **langchain-mcp-adapters** and **MultiServerMCPClient**, supporting SSE, Stdio, and in-process execution.
   - The agent invokes all tools exclusively through the MCP client layer with full operational telemetry (arguments, outputs, latency).

3. **Action Safety Guardrails:**
   - Irreversible actions (such as filing HR tickets or submitting time-off) strictly require **explicit user confirmation** (`confirmed=True`).
   - Unconfirmed actions trigger status `CONFIRMATION_REQUIRED`, halting execution safely and prompting the user for approval.

4. **Multi-Format Policy Corpus & Local Vector Store:**
   - Parses Markdown (`.md`), HTML (`.html`), and plain text (`.txt`).
   - Heading-aware semantic chunking with metadata preservation (Document ID, title, section, source file, snippet).
   - Local ChromaDB vector store with cosine distance and zero cloud dependencies.

5. **Streamlit Web Application & FastAPI Backend:**
   - Real-time interactive chat with expandable citation cards, MCP tool call traces, and architectural step visualizers.
   - Sidebar with pre-loaded one-click demo tasks and persona selectors.
   - Standalone `/chat` and `/health` REST API endpoints.

---

## 🏗️ System Architecture

```
msaie-agentic-HR/
├── design-and-evaluation.md        # Architecture, tool schemas & 25-case evaluation report
├── ai-tooling.md                   # AI tool usage retrospective & debugging analysis
├── deployed.md                     # Live deployment URLs, health endpoints & cold-start notes
├── data/
│   ├── policies/                   # Multi-format HR policies (.md, .html, .txt)
│   ├── employees.json              # Synthetic employee directory records
│   └── tickets.json                # Mock HR ticket store
├── src/
│   ├── config.py                   # Central configuration & environment defaults
│   ├── rag/
│   │   ├── parser.py               # Markdown, HTML, and Text document parser
│   │   ├── chunker.py              # Heading-aware semantic chunker
│   │   ├── vector_store.py         # ChromaDB persistence & fallback embeddings
│   │   └── ingest.py               # Document ingestion & indexing CLI
│   ├── mcp/
│   │   ├── tools.py                # 8 MCP tools implementation & schemas
│   │   ├── server.py               # FastAPI MCP JSON-RPC 2.0 / HTTP server
│   │   └── client.py               # MCP client wrapper & operational telemetry
│   ├── agents/
│   │   ├── state.py                # LangGraph HRAgentState TypedDict
│   │   ├── guardrails.py           # Scope, ambiguity & action safety checks
│   │   ├── llm_provider.py         # Unified LLM provider (API + deterministic fallback)
│   │   ├── policy_agent.py         # RAG agent with query decomposition
│   │   ├── onboarding_agent.py     # New hire checklist & roadmap agent
│   │   ├── employee_agent.py       # PTO, equipment & ticket tool agent
│   │   └── orchestrator.py         # LangGraph StateGraph orchestrator
│   ├── api/
│   │   └── server.py               # FastAPI backend (/chat, /health, /mcp)
│   └── app/
│       └── streamlit_app.py        # Interactive Streamlit frontend UI
├── evaluation/
│   ├── eval_dataset.json           # 25 benchmark evaluation test cases
│   ├── run_eval.py                 # Evaluation benchmark runner & ablation study
│   └── results.md                  # Comprehensive evaluation results report
├── tests/                          # 32 automated unit and integration tests
├── .github/workflows/ci.yml        # GitHub Actions CI/CD pipeline
├── Dockerfile                      # Container build definition
├── render.yaml                     # Render.com deployment manifest
├── Procfile                        # Railway / Heroku deployment descriptor
├── run.sh                          # All-in-one local execution script
└── requirements.txt                # Python dependencies
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Environment Setup
Clone the repository and initialize a virtual environment:
```bash
git clone https://github.com/your-org/msaie-agentic-HR.git
cd msaie-agentic-HR

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
> *Note:* The system uses **OpenRouter** as its primary LLM provider (set `OPENROUTER_API_KEY=your_key` and `OPENROUTER_MODEL=openai/gpt-4o-mini`). The system also includes an intelligent built-in deterministic HR synthesis engine. If no API key is set, all tests, evaluations, and interactive workflows run 100% locally and reproducibly!


### 3. Ingest Policy Documents into ChromaDB
```bash
python src/rag/ingest.py
```
*Output:* Indexes 152 chunks across 11 comprehensive multi-format documents (16,538 words, ~55 standard pages) into `chroma_db/`.

---

## 💻 Running the Application

### Option A: All-in-One Startup Script (Recommended)
Launch the MCP server, FastAPI backend, and Streamlit web app simultaneously:
```bash
./run.sh
```
Open **http://localhost:8501** in your browser.

---

### Option B: Running Individual Services Manually

**1. Start the MCP Server (Port 8001):**
```bash
python src/mcp/server.py
```

**2. Start the FastAPI Backend (Port 8000):**
```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`
- Chat Endpoint: `POST http://localhost:8000/chat`

**3. Start the Streamlit Web Application (Port 8501):**
```bash
streamlit run app.py
```

---

## 🎯 Reproducing the Agentic Demo Tasks

### Demo 1: New Hire Onboarding Roadmap & Email Draft
* **From UI:** Click the sidebar button: **"🚀 Demo 1: Onboarding Roadmap"**.
* **Or via cURL API:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Help with onboarding checklist and draft welcome email for EMP-NEW-01", "employee_id": "EMP-NEW-01"}'
```
* **Observed MCP Sequence:**
  1. `lookup_employee_profile(employee_id="EMP-NEW-01")` &rarr; Retrieves Jordan Hayes' profile and pending checklist items.
  2. `search_policy_documents(query="new hire onboarding equipment allowance benefits 30 days enrollment")` &rarr; Retrieves Day 1 benefits enrollment deadline (`POL-BEN-2024`) and $750 equipment allowance rules (`POL-REMOTE-2024`).
  3. `draft_hr_email(recipient="Jordan Hayes", subject="Welcome to GlobalTech...")` &rarr; Synthesizes onboarding roadmap into an email draft.

---

### Demo 2: PTO Balance Check & Leave Request Guidance (With Action Safety)
* **Step 2A (Unconfirmed Request):**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Submit request to take 3 days PTO for EMP-101", "employee_id": "EMP-101", "confirmed": false}'
```
* **Result:** The **Action Safety Guardrail** intercepts the request with status `CONFIRMATION_REQUIRED`, prompting for user approval before mutating ticket state.

* **Step 2B (Confirmed Request):**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Confirm submission of PTO ticket for 3 days for EMP-101", "employee_id": "EMP-101", "confirmed": true}'
```
* **Result:** Mock ticket `TCK-100X` is created with status `PENDING_MANAGER_APPROVAL` and marked `MOCK_EXECUTED`.

---

## 🛠️ MCP Tool Reference (8 Registered Tools)

| Tool Name | Type | Description |
| :--- | :---: | :--- |
| `search_policy_documents` | RAG / Policy | Semantic vector search across policy corpus with citations and similarity scores. |
| `get_policy_section` | RAG / Policy | Retrieves full text and metadata for a specific policy section and document ID. |
| `lookup_employee_profile` | Structured Data | Fetches role, department, tenure, manager, location, and onboarding checklist. |
| `check_pto_balance` | Tool Execution | Calculates PTO/sick leave balances, tenure tiers, and rollover deadlines. |
| `lookup_benefits_status` | Tool Execution | Retrieves medical, dental, vision, HSA/FSA, and remaining wellness stipend. |
| `create_mock_hr_ticket` | State Action (Safe) | Creates a mock HR ticket; enforces `CONFIRMATION_REQUIRED` if unconfirmed. |
| `check_policy_compliance` | Compliance Audit | Validates proposed actions against remote work, expense caps, or PTO notice rules. |
| `draft_hr_email` | Communication | Formats structured bullet points into a professional HR communication draft. |

---

## 🧪 Testing & CI/CD Pipeline

Run the complete automated test suite (32 unit and integration tests):
```bash
pytest -v
```

### GitHub Actions CI/CD
The automated pipeline defined in `.github/workflows/ci.yml` runs on every push and pull request:
1. Installs pinned dependencies from `requirements.txt`.
2. Ingests and verifies the policy corpus.
3. Runs all 32 automated unit and smoke tests.
4. Executes the 25-case evaluation benchmark runner.
5. Verifies app startup and dynamic MCP tool discovery.

---

## 📊 Evaluation & Benchmark Results

Run the evaluation runner:
```bash
python evaluation/run_eval.py
```

### Summary Benchmark Metrics (25 Test Cases)

| Metric | Result | Target SLA | Status |
| :--- | :---: | :---: | :---: |
| **Workflow Completion Rate** | **100.0%** | &ge; 90.0% | Pass |
| **Tool Selection Accuracy** | **96.0%** | &ge; 90.0% | Pass |
| **Answer Groundedness Recall** | **91.0%** | &ge; 85.0% | Pass |
| **Citation Accuracy Score** | **88.0%** | &ge; 80.0% | Pass |
| **Action Safety Pass Rate** | **100.0%** | 100.0% | Pass |
| **Cold-Start Latency** | **92.03 ms** | &lt; 5000 ms | Pass |
| **Warm Latency (p50)** | **15.84 ms** | &lt; 50 ms | Pass |
| **Warm Latency (p90)** | **42.81 ms** | &lt; 150 ms | Pass |
| **Warm Latency (p95)** | **62.66 ms** | &lt; 250 ms | Pass |

*Detailed benchmark logs and ablation analysis are saved in [evaluation/results.md](file:///Users/2015mbp16gb256gb/Documents/repos/msaie-agentic-HR/evaluation/results.md).*

---

## 🚢 Deployment Guide (Render, Railway, Docker)

### Render.com Deployment
The application is pre-configured with `render.yaml` and deployed at [https://msaie-agentic-hr.onrender.com](https://msaie-agentic-hr.onrender.com):
1. Connect your GitHub repository to Render.
2. Render will automatically detect `render.yaml` and configure:
   - Service: `hr-agentic-web` (Streamlit Web App + LangGraph Orchestrator)
   - Port: `$PORT` (defaults to 8501)
3. Set environment variable `OPENROUTER_API_KEY` (optional; system falls back to built-in synthesis if omitted).
4. **Free Instance Inactivity & Cold-Start Behavior:** This application is deployed on a free instance of Render and spins down during inactivity, which can delay requests by 50 seconds or more while the container provisions and boots. Subsequent requests respond with sub-second latency.

### Docker Deployment
```bash
docker build -t hr-multi-agent .
docker run -p 8501:8501 -p 8000:8000 hr-multi-agent
```
Access the application at `http://localhost:8501`.
