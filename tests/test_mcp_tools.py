import pytest
from src.mcp.client import MCPClient

@pytest.fixture
def mcp_client():
    return MCPClient(prefer_http=False)

def test_mcp_tool_discovery(mcp_client):
    tools = mcp_client.list_tools()
    tool_names = [t["name"] for t in tools]
    assert len(tools) >= 5
    assert "search_policy_documents" in tool_names
    assert "lookup_employee_profile" in tool_names
    assert "check_pto_balance" in tool_names
    assert "create_mock_hr_ticket" in tool_names
    assert "check_policy_compliance" in tool_names

def test_lookup_employee_profile(mcp_client):
    res = mcp_client.call_tool("lookup_employee_profile", {"employee_id": "EMP-101"})
    assert res["status"] == "success"
    profile = res["output"]
    assert profile["full_name"] == "Alice Chen"
    assert profile["department"] == "Engineering"
    assert profile["pto_balance_days"] > 0

def test_check_pto_balance(mcp_client):
    res = mcp_client.call_tool("check_pto_balance", {"employee_id": "EMP-101"})
    assert res["status"] == "success"
    output = res["output"]
    assert "pto_balance_days" in output
    assert "accrual_tier" in output
    assert output["max_rollover_days"] == 5

def test_check_policy_compliance_pto(mcp_client):
    # Compliant request
    res = mcp_client.call_tool("check_policy_compliance", {
        "action_type": "pto_request",
        "details": {
            "employee_id": "EMP-101",
            "days_requested": 2,
            "advance_notice_days": 3
        }
    })
    assert res["status"] == "success"
    assert res["output"]["compliant"] is True

    # Non-compliant request (excessive days beyond balance)
    res_bad = mcp_client.call_tool("check_policy_compliance", {
        "action_type": "pto_request",
        "details": {
            "employee_id": "EMP-101",
            "days_requested": 40,
            "advance_notice_days": 1
        }
    })
    assert res_bad["status"] == "success"
    assert res_bad["output"]["compliant"] is False
    assert len(res_bad["output"]["violations"]) >= 1

def test_create_mock_hr_ticket_safety(mcp_client):
    # Unconfirmed must trigger guardrail
    unconf = mcp_client.call_tool("create_mock_hr_ticket", {
        "employee_id": "EMP-101",
        "ticket_type": "Equipment Stipend",
        "details": "Ergonomic chair request ($350)",
        "confirmed": False
    })
    assert unconf["status"] == "confirmation_required"
    assert unconf["output"]["action_safety"] == "GUARDRAIL_TRIGGERED"

    # Confirmed must execute mock ticket
    conf = mcp_client.call_tool("create_mock_hr_ticket", {
        "employee_id": "EMP-101",
        "ticket_type": "Equipment Stipend",
        "details": "Ergonomic chair request ($350)",
        "confirmed": True
    })
    assert conf["status"] == "success"
    assert conf["output"]["action_safety"] == "MOCK_EXECUTED"
    assert "TCK-" in conf["output"]["ticket_id"]
