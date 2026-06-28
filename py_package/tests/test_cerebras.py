"""Unit tests for the Cerebras provider implementation.

Mocks the httpx REST requests to verify chat completion, streaming, and model listing.
"""

import pytest
from unittest.mock import MagicMock, patch
from everyai_core.providers.cerebras import CerebrasProvider
from everyai_core.types import ChatCompletionResponse


@pytest.fixture
def cerebras_provider():
    return CerebrasProvider(api_key="cbs_test_key")


@patch("httpx.post")
def test_cerebras_chat_non_streaming(mock_post, cerebras_provider):
    """Test successful non-streaming chat request to Cerebras."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-cerebras-123",
        "object": "chat.completion",
        "created": 1600000000,
        "model": "gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from mock Cerebras!"},
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

    response = cerebras_provider.chat(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2
    )

    assert isinstance(response, ChatCompletionResponse)
    assert response.id == "chatcmpl-cerebras-123"
    assert response.choices[0].message["content"] == "Hello from mock Cerebras!"
    assert response.usage.total_tokens == 15
    assert response.provider == "cerebras"

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.cerebras.ai/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer cbs_test_key"
    assert kwargs["json"]["model"] == "gpt-oss-120b"


@patch("httpx.Client")
def test_cerebras_chat_streaming(mock_client_cls, cerebras_provider):
    """Test successful streaming chat request to Cerebras."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.__enter__.return_value = mock_client

    mock_stream_ctx = MagicMock()
    mock_client.stream.return_value = mock_stream_ctx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": "Hello"}}]}',
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": " world!"}}]}',
        b'data: [DONE]'
    ]
    mock_stream_ctx.__enter__.return_value = mock_response

    generator = cerebras_provider.chat(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": "hi"}],
        stream=True
    )

    chunks = list(generator)
    assert len(chunks) == 2
    assert chunks[0].choices[0].message["content"] == "Hello"
    assert chunks[1].choices[0].message["content"] == " world!"
    assert chunks[0].provider == "cerebras"


@patch("httpx.get")
def test_cerebras_list_models(mock_get, cerebras_provider):
    """Test retrieving models list from Cerebras."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "gpt-oss-120b",
                "object": "model",
                "owned_by": "cerebras",
                "context_window": 8192
            }
        ]
    }
    mock_get.return_value = mock_response

    models = cerebras_provider.list_models()
    assert len(models) == 1
    assert models[0].id == "gpt-oss-120b"
    assert models[0].context_length == 8192
    assert models[0].owned_by == "cerebras"
