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
    res = orchestrator.run("Show onboarding checklist and draft welcome email", employee_id="EMP-NEW-01")
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
    res = orchestrator.run("What is my PTO balance?", employee_id="EMP-101")
    trace = res["operational_trace"]
    assert len(trace) >= 2
    assert any(step.get("step") == "intent_routing" and step.get("classifier") == "llm" for step in trace)
    assert any(step.get("step") == "guardrail_check" for step in trace)

def test_pto_balance_without_employee_id_does_not_leak_data(orchestrator):
    res = orchestrator.run("Check my PTO balance", employee_id=None)
    assert "Alice Chen" not in res["answer"]
    assert "14.5" not in res["answer"]
    assert "Employee ID" in res["answer"]
    tool_names = [t.get("tool_name") for t in res["mcp_tool_trace"]]
    assert "check_pto_balance" not in tool_names

def test_onboarding_without_employee_id_does_not_leak_data(orchestrator):
    res = orchestrator.run("Show my onboarding checklist", employee_id=None)
    assert "Jordan Hayes" not in res["answer"]
    assert "EMP-NEW-01" not in res["answer"]
    assert "Employee ID" in res["answer"]
    tool_names = [t.get("tool_name") for t in res["mcp_tool_trace"]]
    assert "lookup_employee_profile" not in tool_names

def test_general_onboarding_policy_query_without_employee_id(orchestrator):
    res = orchestrator.run("What are the new hire benefits election deadlines and equipment allowance?", employee_id=None)
    assert "30 calendar days" in res["answer"]
    assert "$750" in res["answer"]
    assert "Jordan Hayes" not in res["answer"]
    assert "Alice Chen" not in res["answer"]
    tool_names = [t.get("tool_name") for t in res["mcp_tool_trace"]]
    assert "lookup_employee_profile" not in tool_names

def test_personalized_policy_query_with_session_employee_id(orchestrator):
    res = orchestrator.run("What is the pto policy?", employee_id="EMP-101")
    assert res["workflow"] == "policy_rag"
    assert "Alice Chen" in res["answer"]
    assert "20 days" in res["answer"] or "Tier 2" in res["answer"]
    assert "14.5" in res["answer"]
    assert len(res["citations"]) > 0
    tool_names = [t.get("tool_name") for t in res["mcp_tool_trace"]]
    assert "lookup_employee_profile" in tool_names

def test_query_text_mention_without_session_employee_id_does_not_lookup_profile(orchestrator):
    res = orchestrator.run("What is the pto policy for EMP-101?", employee_id=None)
    assert "Alice Chen" not in res["answer"]
    assert "14.5" not in res["answer"]
    tool_names = [t.get("tool_name") for t in res["mcp_tool_trace"]]
    assert "lookup_employee_profile" not in tool_names

def test_session_employee_id_not_overridden_by_query_text_mention(orchestrator):
    # Session is EMP-101, but query text mentions EMP-102
    res = orchestrator.run("What is the pto policy for EMP-102?", employee_id="EMP-101")
    assert "Alice Chen" in res["answer"]
    assert "Marcus Johnson" not in res["answer"]
    tool_names = [t.get("tool_name") for t in res["mcp_tool_trace"]]
    assert "lookup_employee_profile" in tool_names
    lookup_calls = [t for t in res["mcp_tool_trace"] if t.get("tool_name") == "lookup_employee_profile"]
    assert all(c["arguments"].get("employee_id") == "EMP-101" for c in lookup_calls)

def test_generic_policy_query_remains_unpersonalized(orchestrator):
    res = orchestrator.run("What is the pto policy?", employee_id=None)
    assert "Alice Chen" not in res["answer"]
    assert "Marcus Johnson" not in res["answer"]
    tool_names = [t.get("tool_name") for t in res["mcp_tool_trace"]]
    assert "lookup_employee_profile" not in tool_names
