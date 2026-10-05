# Deployment Information & Service Endpoints

This document provides deployment URLs, health endpoints, container execution details, and cold-start characteristics for the **GlobalTech HR Multi-Agent Automation System**.

---

## 1. Live Deployment vs. Local Endpoints

> [!IMPORTANT]
> **Live Deployment Scope:**
> **Only the interactive Streamlit web application** is deployed and accessible at [https://msaie-agentic-hr.onrender.com](https://msaie-agentic-hr.onrender.com).
>
> On Render, the free-tier web service runs a single web process bound to `$PORT` executing `streamlit run app.py`. Because Streamlit is a Single Page Application (SPA), all HTTP requests to subpaths (such as `/health`, `/chat`, or `/docs`) sent to `https://msaie-agentic-hr.onrender.com` are captured by Streamlit's internal router and return the Streamlit frontend HTML application.
>
> **The REST API endpoints (`/health`, `/chat`, `/docs`) and the FastMCP tool server (`/mcp`) are only available on local deployment.**

| Service / Interface | Deployed Public URL | Local Development URL | Availability / Notes |
| :--- | :--- | :--- | :--- |
| **Interactive Web Application (Streamlit)** | [https://msaie-agentic-hr.onrender.com](https://msaie-agentic-hr.onrender.com) | [http://localhost:8501](http://localhost:8501) | **Available Deployed & Locally**. Full interactive chat UI with persona switcher, 1-click demo tasks, citation cards, and operational traces. |
| **Service Health Check Endpoint (`/health`)** | *N/A (Returns Streamlit app)* | [http://localhost:8000/health](http://localhost:8000/health) | **Local Deployment Only**. FastAPI JSON endpoint returning system status, vector store chunk count (152 chunks), and MCP connectivity. |
| **Chat & Multi-Agent API Endpoint (`/chat`)** | *N/A (Returns Streamlit app)* | [http://localhost:8000/chat](http://localhost:8000/chat) | **Local Deployment Only**. FastAPI `POST` endpoint accepting user inquiries and returning answers, citations, and MCP tool traces. |
| **Interactive API Documentation (`/docs`)** | *N/A (Returns Streamlit app)* | [http://localhost:8000/docs](http://localhost:8000/docs) | **Local Deployment Only**. Swagger UI for interactive inspection of REST API endpoints. |
| **MCP Tool Server (`/mcp`)** | *N/A (Returns Streamlit app)* | [http://localhost:8001/mcp](http://localhost:8001/mcp) | **Local Deployment Only**. FastMCP JSON-RPC / Streamable HTTP endpoint for the registered MCP tools. |

---

## 2. Health Endpoint Specification (Local Deployment)

When running the system locally (via `./run.sh` or `python src/api/server.py`), the FastAPI health endpoint provides automated verification of the multi-agent application and its dependent subsystems on port **8000**:

### Request:
```bash
curl -X GET http://localhost:8000/health
```

### Response Payload:
```json
{
  "status": "healthy",
  "service": "hr-agentic-rag-system",
  "mcp_server_status": "connected_http",
  "vector_store_chunks": 152,
  "supported_workflows": [
    "policy_rag",
    "onboarding",
    "pto_management",
    "remote_work_eligibility",
    "expense_compliance"
  ],
  "version": "1.0.0"
}
```

> [!NOTE]
> If you query `https://msaie-agentic-hr.onrender.com/health` or `http://localhost:8501/health`, the response will be the Streamlit HTML page because that request is being handled by Streamlit's webserver (which only handles SPA pages and internal health checks at `/_stcore/health`). The JSON health check endpoint is served by FastAPI on port `8000`.

---

## 3. Free-Tier Cold-Start Characteristics & Notes

### 3.1 Container Sleep & Wake-up Behavior
- **Inactivity Spin-Down:** On Render.com's free tier, web services automatically spin down to 0 active container instances after **15 minutes of inactivity** to conserve compute resources.
- **Cold-Start Duration:** When a new request arrives after dormancy, Render provisions a container instance. This introduces a one-time cold-start delay of **50 to 90 seconds** while the platform spins back up, unpacks the container image, and binds to the assigned `$PORT`.
- **Subsequent (Warm) Latency:** Once the container is awake, all subsequent requests experience sub-second response times:
  - Vector search latency: **~0.78 ms**
  - Warm agent execution latency (p50): **15.83 ms**
  - Warm agent execution latency (p95): **31.08 ms**

### 3.2 Cold-Start Optimization in System Design
To minimize cold-start impact on free tiers:
1. **Pre-Indexed Knowledge Base:** The policy corpus is parsed and indexed into ChromaDB during Docker build time (`RUN python src/rag/ingest.py`). The vector database is baked directly into the image, eliminating runtime indexing delays.
2. **Deterministic Fallback Embeddings:** The system uses zero-download deterministic fallback embeddings for local vector lookups, avoiding multi-gigabyte HuggingFace model downloads during container initialization.
3. **Connection Caching (`@st.cache_resource`):** ChromaDB client connections and orchestrator instances are cached in memory across Streamlit reactive frames to prevent expensive SQLite re-openings.

### 3.3 Running the Full Multi-Service Stack Locally
To run both the Streamlit UI and the backend API services without free-tier cold starts or port restrictions:
```bash
./run.sh
```
This script launches:
1. **FastMCP Server** on port `8001` (`http://localhost:8001/mcp`)
2. **FastAPI Backend** on port `8000` (`http://localhost:8000/health`, `http://localhost:8000/chat`, `http://localhost:8000/docs`)
3. **Streamlit Web Application** on port `8501` (`http://localhost:8501`)

---

## 4. One-Click Reproducible Demo Commands (Local Deployment)

Ensure the local services are running via `./run.sh`, then execute the following commands in your terminal:

### Test Health Endpoint:
```bash
curl -s http://localhost:8000/health | jq .
```

### Run Policy RAG Query via API:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the international remote work guidelines and how many days are allowed per year?"
  }' | jq .
```

### Run PTO Balance Check for Active Employee:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Check my PTO balance for EMP-101",
    "employee_id": "EMP-101"
  }' | jq .
```

### Run Action Safety Guardrail Check (Unconfirmed Request):
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Submit request to take 3 days PTO for EMP-101",
    "employee_id": "EMP-101",
    "confirmed": false
  }' | jq .
```
*(Notice that the action safety guardrail intercepts the request with status `CONFIRMATION_REQUIRED` without modifying system state).*
