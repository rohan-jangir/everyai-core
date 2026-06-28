"""Unit tests for the Groq provider implementation.

Mocks the httpx REST requests to verify chat completion, streaming, and model listing.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from everyai_core.providers.groq import GroqProvider
from everyai_core.types import ChatCompletionResponse


@pytest.fixture
def groq_provider():
    return GroqProvider(api_key="gsk_test_key")


@patch("httpx.post")
def test_groq_chat_non_streaming(mock_post, groq_provider):
    """Test successful non-streaming chat request to Groq."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-groq-123",
        "object": "chat.completion",
        "created": 1600000000,
        "model": "llama3-8b-8192",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from mock Groq!"},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }
    mock_post.return_value = mock_response

    response = groq_provider.chat(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7
    )

    assert isinstance(response, ChatCompletionResponse)
    assert response.id == "chatcmpl-groq-123"
    assert response.choices[0].message["content"] == "Hello from mock Groq!"
    assert response.usage.total_tokens == 15
    assert response.provider == "groq"

    # Verify endpoint and headers passed
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.groq.com/openai/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer gsk_test_key"
    assert kwargs["json"]["model"] == "llama3-8b-8192"


@patch("httpx.Client")
def test_groq_chat_streaming(mock_client_cls, groq_provider):
    """Test successful streaming chat request to Groq."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.__enter__.return_value = mock_client

    mock_stream_ctx = MagicMock()
    mock_client.stream.return_value = mock_stream_ctx

    mock_response = MagicMock()
    mock_response.status_code = 200
    
    # Mock chunks of Server-Sent Events (SSE)
    mock_response.iter_lines.return_value = [
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": "Hello"}}]}',
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": " world!"}}]}',
        b'data: [DONE]'
    ]
    mock_stream_ctx.__enter__.return_value = mock_response

    generator = groq_provider.chat(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": "hi"}],
        stream=True
    )

    chunks = list(generator)
    assert len(chunks) == 2
    assert chunks[0].choices[0].message["content"] == "Hello"
    assert chunks[1].choices[0].message["content"] == " world!"
    assert chunks[0].provider == "groq"


@patch("httpx.get")
def test_groq_list_models(mock_get, groq_provider):
    """Test retrieving models list from Groq."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "llama3-8b-8192",
                "object": "model",
                "owned_by": "groq",
                "context_window": 8192
            }
        ]
    }
    mock_get.return_value = mock_response

    models = groq_provider.list_models()
    assert len(models) == 1
    assert models[0].id == "llama3-8b-8192"
    assert models[0].context_length == 8192
    assert models[0].owned_by == "groq"
