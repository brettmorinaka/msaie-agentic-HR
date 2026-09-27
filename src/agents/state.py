from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

class TraceStep(TypedDict):
    step_name: str
    action_type: str
    details: Dict[str, Any]
    timestamp: str

class Citation(TypedDict):
    document_id: str
    document_title: str
    section_title: str
    source_file: str
    snippet: str
    similarity_score: float

class HRAgentState(TypedDict):
    # User Input & Session Context
    user_query: str
    employee_id: Optional[str]
    session_id: str
    confirmed: bool

    # Intent & Routing
    workflow: str  # "policy_rag", "onboarding", "employee_workflow", "clarification", "out_of_scope"
    intent_reasoning: str

    # Retrieval & RAG
    retrieved_chunks: List[Dict[str, Any]]
    citations: List[Citation]
    query_rewrites: List[str]

    # Tool Execution & MCP
    tool_calls: List[Dict[str, Any]]
    operational_trace: List[Dict[str, Any]]

    # Response & Synthesis
    facts: List[str]
    recommendations: List[str]
    action_safety_status: str  # "SAFE", "CONFIRMATION_REQUIRED", "MOCK_EXECUTED"
    final_response: str
    error: Optional[str]
