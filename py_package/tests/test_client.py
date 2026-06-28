"""Unit tests for the EveryAI client orchestrator.

Verifies configuration, provider access, environment loaders, and exception flow.
"""

import os
import pytest
from everyai_core import EveryAI, ConfigurationError


def test_client_init_with_keys():
    """Test client initialization with manual API key mapping."""
    client = EveryAI(api_keys={"groq": "gsk_test_key"})
    
    assert "groq" in client.list_providers()
    # Ensure properties lazily load provider with the correct key
    assert client.groq.api_key == "gsk_test_key"


def test_client_init_with_env(monkeypatch):
    """Test environment variable fallback loading."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_env_key")
    
    client = EveryAI()
    assert client.groq.api_key == "gsk_env_key"


def test_client_missing_key_raises_error(monkeypatch):
    """Test that missing keys properly raise ConfigurationError."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    
    client = EveryAI()
    with pytest.raises(ConfigurationError) as exc_info:
        _ = client.groq
    assert "API Key for provider 'groq' is not set" in str(exc_info.value)


def test_list_providers():
    """Test retrieving lists of registered providers."""
    client = EveryAI()
    providers = client.list_providers()
    
    assert "groq" in providers
    assert "openrouter" in providers
    assert "huggingface" in providers


def test_unsupported_provider():
    """Test that requesting an unsupported provider throws a ValueError."""
    client = EveryAI()
    with pytest.raises(ValueError) as exc_info:
        client.get_provider("nonexistent")
    assert "Unsupported provider: 'nonexistent'" in str(exc_info.value)
