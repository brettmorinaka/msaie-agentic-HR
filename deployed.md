# Deployment Information & Service Endpoints

This document provides deployment URLs, health endpoints, container execution details, and cold-start characteristics for the **GlobalTech HR Multi-Agent Automation System**.

---

## 1. Live Deployment Endpoints

| Service / Interface | Deployed Public URL | Local Development URL | Description |
| :--- | :--- | :--- | :--- |
| **Interactive Web Application (Streamlit)** | [https://msaie-agentic-hr.onrender.com](https://msaie-agentic-hr.onrender.com) | [http://localhost:8501](http://localhost:8501) | Full interactive chat UI with persona switcher, 1-click demo tasks, citation cards, and operational traces. |
| **Service Health Check Endpoint** | [https://msaie-agentic-hr.onrender.com/health](https://msaie-agentic-hr.onrender.com/health) | [http://localhost:8000/health](http://localhost:8000/health) | JSON endpoint returning system status, vector store chunk count (37 chunks), and MCP connectivity. |
| **Chat & Multi-Agent API Endpoint** | [https://msaie-agentic-hr.onrender.com/chat](https://msaie-agentic-hr.onrender.com/chat) | [http://localhost:8000/chat](http://localhost:8000/chat) | `POST` endpoint accepting user inquiries and returning answers, citations, and MCP tool traces. |
| **Interactive API Documentation** | [https://msaie-agentic-hr.onrender.com/docs](https://msaie-agentic-hr.onrender.com/docs) | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for interactive testing of REST API endpoints. |
| **MCP Tool Server** | [https://msaie-agentic-hr.onrender.com/mcp](https://msaie-agentic-hr.onrender.com/mcp) | [http://localhost:8001/mcp](http://localhost:8001/mcp) | JSON-RPC 2.0 / Streamable HTTP endpoint for the 8 registered MCP tools. |

---

## 2. Health Endpoint Specification

The health endpoint provides automated verification of the multi-agent application and its dependent subsystems:

### Request:
```bash
curl -X GET https://msaie-agentic-hr.onrender.com/health
```

### Response Payload:
```json
{
  "status": "healthy",
  "app": "GlobalTech HR Multi-Agent Automation System",
  "version": "1.0.0",
  "vector_store_chunks": 37,
  "mcp_server_connected": true,
  "registered_tools_count": 8,
  "timestamp": "2026-10-02T20:30:00Z"
}
```

---

## 3. Free-Tier Cold-Start Characteristics & Notes

### 3.1 Container Sleep & Wake-up Behavior
- **Inactivity Spin-Down:** On Render.com / Railway free tiers, web services automatically spin down to 0 active container instances after **15 minutes of inactivity** to conserve compute resources.
- **Cold-Start Duration:** When a new request arrives after a period of dormancy, the hosting platform boots up a new container instance. This typically introduces a one-time cold-start delay of **50 to 90 seconds** while the platform provisions memory, unpacks the container image, and binds to the assigned `$PORT`.
- **Subsequent (Warm) Latency:** Once the container is awake, all subsequent requests experience sub-second response times:
  - Vector search latency: **~0.78 ms**
  - Warm agent execution latency (p50): **15.33 ms**
  - Warm agent execution latency (p95): **61.61 ms**

### 3.2 Cold-Start Optimization in System Design
To minimize cold-start impact on free tiers:
1. **Pre-Indexed Knowledge Base:** The policy corpus is parsed and indexed into ChromaDB during Docker build time (`RUN python src/rag/ingest.py`). The vector database is baked directly into the image, eliminating runtime indexing delays.
2. **Deterministic Fallback Embeddings:** The system uses zero-download deterministic fallback embeddings for local vector lookups, avoiding multi-gigabyte HuggingFace model downloads during container initialization.
3. **Connection Caching (`@st.cache_resource`):** ChromaDB client connections and orchestrator instances are cached in memory across Streamlit reactive frames to prevent expensive SQLite re-openings.

### 3.3 Strategies to Mitigate Free-Tier Dormancy
If persistent instant-wake behavior is desired on free hosting:
- **Automated Uptime Ping:** Configure a free monitoring service (such as [UptimeRobot](https://uptimerobot.com) or [Cron-Job.org](https://cron-job.org)) to perform a lightweight `GET` request to `/health` every 10–14 minutes. This prevents the container from entering dormancy.
- **Local Execution:** If free-tier cold starts are inconvenient during grading or demonstration, the entire multi-service stack can be run locally in under 3 seconds using `./run.sh`.

---

## 4. One-Click Reproducible Demo Commands

### Test Health Endpoint:
```bash
curl -s https://msaie-agentic-hr.onrender.com/health | jq .
```

### Run Policy RAG Query via API:
```bash
curl -X POST https://msaie-agentic-hr.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the international remote work guidelines and how many days are allowed per year?"
  }' | jq .
```

### Run PTO Balance Check for Active Employee:
```bash
curl -X POST https://msaie-agentic-hr.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Check my PTO balance for EMP-101",
    "employee_id": "EMP-101"
  }' | jq .
```

### Run Action Safety Guardrail Check (Unconfirmed Request):
```bash
curl -X POST https://msaie-agentic-hr.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Submit request to take 3 days PTO for EMP-101",
    "employee_id": "EMP-101",
    "confirmed": false
  }' | jq .
```
*(Notice that the action safety guardrail intercepts the request with status `CONFIRMATION_REQUIRED` without modifying system state).*
