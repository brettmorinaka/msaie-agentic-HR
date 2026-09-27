import pytest
from fastapi.testclient import TestClient
from src.api.server import app

client = TestClient(app)

def test_api_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "vector_store_chunks" in data
    assert data["vector_store_chunks"] > 0
    assert "supported_workflows" in data

def test_api_chat_endpoint_policy():
    payload = {
        "message": "What is the policy for international remote work?",
        "employee_id": "EMP-101",
        "confirmed": False
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["citations"]) > 0
    assert "operational_trace" in data
    assert "mcp_tool_trace" in data

def test_api_chat_endpoint_empty_message():
    payload = {"message": "   "}
    response = client.post("/chat", json=payload)
    assert response.status_code == 400
