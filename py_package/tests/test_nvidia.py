"""Unit tests for the Nvidia provider implementation.

Mocks the httpx REST requests to verify chat completion, streaming, and model listing.
"""

import pytest
from unittest.mock import MagicMock, patch
from everyai_core.providers.nvidia import NvidiaProvider
from everyai_core.types import ChatCompletionResponse


@pytest.fixture
def nvidia_provider():
    return NvidiaProvider(api_key="nv_test_key")


@patch("httpx.post")
def test_nvidia_chat_non_streaming(mock_post, nvidia_provider):
    """Test successful non-streaming chat request to Nvidia."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-nvidia-123",
        "object": "chat.completion",
        "created": 1600000000,
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from mock Nvidia NIM!"},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 7,
            "total_tokens": 22
        }
    }
    mock_post.return_value = mock_response

    response = nvidia_provider.chat(
        model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.6,
        top_p=0.95
    )

    assert isinstance(response, ChatCompletionResponse)
    assert response.id == "chatcmpl-nvidia-123"
    assert response.choices[0].message["content"] == "Hello from mock Nvidia NIM!"
    assert response.usage.total_tokens == 22
    assert response.provider == "nvidia"

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer nv_test_key"
    assert kwargs["json"]["model"] == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


@patch("httpx.Client")
def test_nvidia_chat_streaming(mock_client_cls, nvidia_provider):
    """Test successful streaming chat request to Nvidia NIM."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.__enter__.return_value = mock_client

    mock_stream_ctx = MagicMock()
    mock_client.stream.return_value = mock_stream_ctx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": "Hello"}}]}',
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": " Nvidia!"}}]}',
        b'data: [DONE]'
    ]
    mock_stream_ctx.__enter__.return_value = mock_response

    generator = nvidia_provider.chat(
        model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        messages=[{"role": "user", "content": "hi"}],
        stream=True
    )

    chunks = list(generator)
    assert len(chunks) == 2
    assert chunks[0].choices[0].message["content"] == "Hello"
    assert chunks[1].choices[0].message["content"] == " Nvidia!"
    assert chunks[0].provider == "nvidia"


@patch("httpx.get")
def test_nvidia_list_models(mock_get, nvidia_provider):
    """Test retrieving models list from Nvidia integrate API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                "object": "model",
                "owned_by": "nvidia",
                "context_window": 32768
            }
        ]
    }
    mock_get.return_value = mock_response

    models = nvidia_provider.list_models()
    assert len(models) == 1
    assert models[0].id == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    assert models[0].context_length == 32768
    assert models[0].owned_by == "nvidia"
