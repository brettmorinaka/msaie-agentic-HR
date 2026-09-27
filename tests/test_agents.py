import pytest
from src.agents.orchestrator import HROrchestrator

@pytest.fixture
def orchestrator():
    return HROrchestrator()

def test_policy_rag_query(orchestrator):
    res = orchestrator.run("What are the international remote work guidelines?")
    assert res["workflow"] == "policy_rag"
    assert len(res["citations"]) > 0
    assert "30" in res["answer"] or "calendar days" in res["answer"]
    assert len(res["mcp_tool_trace"]) >= 1

def test_complex_multi_document_query(orchestrator):
    res = orchestrator.run("Can I expense meals while working remotely on PTO from France?")
    assert len(res["citations"]) >= 2
    assert "non-reimbursable" in res["answer"].lower() or "strictly" in res["answer"].lower()
    # Verified that both POL-REMOTE-2024 and POL-EXP-2024 are referenced
    doc_ids = [c["document_id"] for c in res["citations"]]
    assert "POL-REMOTE-2024" in doc_ids or "POL-EXP-2024" in doc_ids

def test_onboarding_agent_workflow(orchestrator):
    res = orchestrator.run("Show onboarding checklist and draft welcome email for EMP-NEW-01")
    assert res["workflow"] == "onboarding"
    assert "EMP-NEW-01" in res["answer"]
    assert "Jordan Hayes" in res["answer"]
    assert len(res["mcp_tool_trace"]) >= 2

def test_out_of_scope_guardrail(orchestrator):
    res = orchestrator.run("How do I bake chocolate chip cookies?")
    assert res["workflow"] == "out_of_scope"
    assert "cannot assist" in res["answer"].lower() or "scope" in res["answer"].lower()
    assert len(res["mcp_tool_trace"]) == 0

def test_operational_trace_structure(orchestrator):
    res = orchestrator.run("What is my PTO balance for EMP-101?")
    trace = res["operational_trace"]
    assert len(trace) >= 2
    assert any(step.get("step") == "intent_routing" for step in trace)
    assert any(step.get("step") == "guardrail_check" for step in trace)
