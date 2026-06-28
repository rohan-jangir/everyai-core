"""Unit tests for the OpenRouter provider implementation.

Mocks the httpx REST requests to verify chat completion, streaming, and model listing.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from everyai_core.providers.openrouter import OpenRouterProvider
from everyai_core.types import ChatCompletionResponse


@pytest.fixture
def or_provider():
    return OpenRouterProvider(api_key="or_test_key")


@patch("httpx.post")
def test_openrouter_chat_non_streaming(mock_post, or_provider):
    """Test successful non-streaming chat request to OpenRouter."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-or-123",
        "object": "chat.completion",
        "created": 1600000000,
        "model": "google/gemini-flash-1.5",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from OpenRouter!"},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 8,
            "total_tokens": 23
        }
    }
    mock_post.return_value = mock_response

    response = or_provider.chat(
        model="google/gemini-flash-1.5",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7
    )

    assert isinstance(response, ChatCompletionResponse)
    assert response.id == "chatcmpl-or-123"
    assert response.choices[0].message["content"] == "Hello from OpenRouter!"
    assert response.usage.total_tokens == 23
    assert response.provider == "openrouter"

    # Verify endpoint and headers passed
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://openrouter.ai/api/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer or_test_key"
    assert kwargs["headers"]["HTTP-Referer"] == "https://github.com/rohan-jangir/everyai-core"
    assert kwargs["json"]["model"] == "google/gemini-flash-1.5"


@patch("httpx.Client")
def test_openrouter_chat_streaming(mock_client_cls, or_provider):
    """Test successful streaming chat request to OpenRouter."""
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

    generator = or_provider.chat(
        model="google/gemini-flash-1.5",
        messages=[{"role": "user", "content": "hi"}],
        stream=True
    )

    chunks = list(generator)
    assert len(chunks) == 2
    assert chunks[0].choices[0].message["content"] == "Hello"
    assert chunks[1].choices[0].message["content"] == " world!"
    assert chunks[0].provider == "openrouter"


@patch("httpx.get")
def test_openrouter_list_models(mock_get, or_provider):
    """Test retrieving models list from OpenRouter."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "google/gemini-flash-1.5",
                "name": "Gemini 1.5 Flash",
                "context_length": 1048576,
                "owned_by": "google"
            }
        ]
    }
    mock_get.return_value = mock_response

    models = or_provider.list_models()
    assert len(models) == 1
    assert models[0].id == "google/gemini-flash-1.5"
    assert models[0].name == "Gemini 1.5 Flash"
    assert models[0].context_length == 1048576
    assert models[0].owned_by == "google"
