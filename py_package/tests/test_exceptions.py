"""Unit tests for the EveryAI exception mapping and response parsing.

Verifies raise_for_status logic, suggestion messages formatting, and schema compatibility.
"""

import pytest
from everyai_core.exceptions import (
    raise_for_status,
    ConfigurationError,
    ModelNotFoundError,
    NetworkError,
    AuthenticationError,
    RateLimitError,
    ContextLengthExceededError,
    InvalidRequestError,
    ProviderServerError,
    ProviderError,
)


def test_client_side_error_suggestions():
    """Verify that client-side system failures append troubleshooting instructions."""
    config_err = ConfigurationError("Missing GROQ_API_KEY")
    assert "[Configuration Error] Missing GROQ_API_KEY" in str(config_err)
    assert "[Suggestion]:" in str(config_err)

    model_err = ModelNotFoundError("Unsupported model: gpt-2")
    assert "[Model Not Found] Unsupported model: gpt-2" in str(model_err)
    assert "[Suggestion]:" in str(model_err)

    net_err = NetworkError("Connection timed out")
    assert "[Network Connection Error] Connection timed out" in str(net_err)
    assert "[Suggestion]:" in str(net_err)


def test_provider_side_error_raw_messages():
    """Verify that remote provider exceptions preserve the raw API message without guesses."""
    auth_err = AuthenticationError("Key is expired or revoked", provider="groq", status_code=401)
    # Checks that it outputs the exact raw text and status
    assert "[GROQ API Error] (Status 401): Key is expired or revoked" == str(auth_err)
    # Ensure client suggestions are NOT included for server side errors
    assert "Suggestion" not in str(auth_err)


def test_raise_for_status_groq_mapping():
    """Test mapping HTTP responses from the Groq provider."""
    # 401 Unauthorized -> AuthenticationError
    payload_401 = '{"error": {"message": "Invalid API Key supplied", "type": "invalid_request_error"}}'
    with pytest.raises(AuthenticationError) as exc:
        raise_for_status("groq", 401, payload_401)
    assert exc.value.status_code == 401
    assert "Invalid API Key supplied" in str(exc.value)

    # 429 Too Many Requests -> RateLimitError
    payload_429 = '{"error": {"message": "Rate limit exceeded for rpm", "code": "rate_limit_exceeded"}}'
    with pytest.raises(RateLimitError) as exc:
        raise_for_status("groq", 429, payload_429)
    assert exc.value.status_code == 429
    assert "Rate limit exceeded for rpm" in str(exc.value)

    # 400 Bad Request with context limit -> ContextLengthExceededError
    payload_context = '{"error": {"message": "The input tokens exceed context window limit of 8192"}}'
    with pytest.raises(ContextLengthExceededError) as exc:
        raise_for_status("groq", 400, payload_context)
    assert "context window limit of 8192" in str(exc.value)

    # 400 Bad Request general -> InvalidRequestError
    payload_bad = '{"error": {"message": "temperature must be <= 2.0"}}'
    with pytest.raises(InvalidRequestError) as exc:
        raise_for_status("groq", 400, payload_bad)
    assert "temperature must be <= 2.0" in str(exc.value)

    # 503 Internal Server Error -> ProviderServerError
    with pytest.raises(ProviderServerError) as exc:
        raise_for_status("groq", 503, "Internal server is overloaded.")
    assert "Internal server is overloaded." in str(exc.value)


def test_raise_for_status_huggingface_mapping():
    """Test mapping HTTP responses from the Hugging Face provider."""
    # Hugging Face list error format
    payload_list = '{"error": ["Model is currently loading", "estimated_time: 20s"]}'
    with pytest.raises(ProviderServerError) as exc:
        raise_for_status("huggingface", 503, payload_list)
    assert "Model is currently loading, estimated_time: 20s" in str(exc.value)

    # Hugging Face standard error text
    payload_auth = '{"error": "Authorization token is invalid."}'
    with pytest.raises(AuthenticationError) as exc:
        raise_for_status("huggingface", 401, payload_auth)
    assert "Authorization token is invalid." in str(exc.value)
