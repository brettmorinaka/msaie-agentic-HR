import sys
import uvicorn
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import API_HOST, API_PORT, CHROMA_PERSIST_DIR
from src.agents.orchestrator import HROrchestrator
from src.mcp.client import MCPClient
from src.mcp.server import app as mcp_app
from src.rag.vector_store import PolicyVectorStore

app = FastAPI(
    title="HR Multi-Agent Automation System API",
    description="LangGraph-powered HR multi-agent orchestrator with MCP tools, policy RAG, and self-service workflows.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator instance
orchestrator = HROrchestrator()

class ChatRequest(BaseModel):
    message: str
    employee_id: Optional[str] = None
    session_id: Optional[str] = "default-session"
    confirmed: Optional[bool] = False

class ChatResponse(BaseModel):
    query: str
    answer: str
    citations: List[Dict[str, Any]]
    action_safety: str
    workflow: str
    operational_trace: List[Dict[str, Any]]
    mcp_tool_trace: List[Dict[str, Any]]

@app.get("/health")
async def health_check():
    """
    Health check returning system status, vector store count, and MCP connectivity.
    """
    mcp_client = orchestrator.mcp
    is_mcp_live = mcp_client.is_server_reachable()

    try:
        vs = PolicyVectorStore(persist_dir=str(CHROMA_PERSIST_DIR), use_fallback_embeddings=True)
        chunks_count = vs.count()
    except Exception:
        chunks_count = 0

    return {
        "status": "healthy",
        "service": "hr-agentic-rag-system",
        "mcp_server_status": "connected_http" if is_mcp_live else "in_process_active",
        "vector_store_chunks": chunks_count,
        "supported_workflows": [
            "policy_rag",
            "onboarding",
            "pto_management",
            "remote_work_eligibility",
            "expense_compliance"
        ],
        "version": "1.0.0"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Receives user requests and executes the LangGraph multi-agent system.
    Returns the answer, citations, snippets, and concise tool-call trace.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message field cannot be empty.")

    try:
        result = orchestrator.run(
            user_query=request.message,
            employee_id=request.employee_id,
            session_id=request.session_id or "default-session",
            confirmed=bool(request.confirmed)
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {str(e)}")

# Mount MCP sub-routes for unified single-service deployments
app.mount("/mcp-service", mcp_app)

def start():
    uvicorn.run("src.api.server:app", host=API_HOST, port=API_PORT, reload=False)

if __name__ == "__main__":
    start()
