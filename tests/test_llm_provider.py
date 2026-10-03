from unittest.mock import patch, MagicMock
import pytest
from src.agents.llm_provider import LLMProvider

def test_llm_provider_initialization_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey123456789")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")

    provider = LLMProvider()
    assert provider.openrouter_key == "sk-or-v1-testkey123456789"
    assert provider.active_provider == "openrouter"
    assert provider.model == "openai/gpt-4o-mini"

def test_llm_provider_openrouter_successful_generate(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey123456789")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")

    provider = LLMProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Employees may work remotely internationally for up to 30 calendar days per year (POL-REMOTE-2024)."
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = provider.generate("How many days of international remote work?", "You are an HR Assistant.")
        assert "30 calendar days" in res
        assert mock_post.called
        # Check call arguments
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer sk-or-v1-testkey123456789"
        assert call_kwargs["json"]["model"] == "openai/gpt-4o-mini"
        assert call_kwargs["json"]["messages"][1]["content"] == "How many days of international remote work?"

def test_llm_provider_openrouter_fallback_on_api_error(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey123456789")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    provider = LLMProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.generate("What is the annual PTO accrual for an employee with 3 years of service?")
        # Should gracefully fall back to deterministic synthesis without raising an unhandled exception
        assert "Tier 2" in res or "20 days" in res

def test_llm_provider_openrouter_fallback_on_exception(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey123456789")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    provider = LLMProvider()

    with patch("httpx.Client.post", side_effect=Exception("Connection timed out")):
        res = provider.generate("How many days of international remote work are allowed per year?")
        assert "30 calendar days" in res
