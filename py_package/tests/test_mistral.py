"""Unit tests for the Mistral provider implementation.

Mocks the httpx REST requests to verify chat completion, streaming, and model listing.
"""

import pytest
from unittest.mock import MagicMock, patch
from everyai_core.providers.mistral import MistralProvider
from everyai_core.types import ChatCompletionResponse


@pytest.fixture
def mistral_provider():
    return MistralProvider(api_key="mst_test_key")


@patch("httpx.post")
def test_mistral_chat_non_streaming(mock_post, mistral_provider):
    """Test successful non-streaming chat request to Mistral."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-mistral-123",
        "object": "chat.completion",
        "created": 1600000000,
        "model": "mistral-large-latest",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from mock Mistral!"},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 6,
            "total_tokens": 18
        }
    }
    mock_post.return_value = mock_response

    response = mistral_provider.chat(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7
    )

    assert isinstance(response, ChatCompletionResponse)
    assert response.id == "chatcmpl-mistral-123"
    assert response.choices[0].message["content"] == "Hello from mock Mistral!"
    assert response.usage.total_tokens == 18
    assert response.provider == "mistral"

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.mistral.ai/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer mst_test_key"
    assert kwargs["json"]["model"] == "mistral-large-latest"


@patch("httpx.Client")
def test_mistral_chat_streaming(mock_client_cls, mistral_provider):
    """Test successful streaming chat request to Mistral."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.__enter__.return_value = mock_client

    mock_stream_ctx = MagicMock()
    mock_client.stream.return_value = mock_stream_ctx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": "Hi"}}]}',
        b'data: {"id": "1", "choices": [{"index": 0, "delta": {"content": " there!"}}]}',
        b'data: [DONE]'
    ]
    mock_stream_ctx.__enter__.return_value = mock_response

    generator = mistral_provider.chat(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": "hi"}],
        stream=True
    )

    chunks = list(generator)
    assert len(chunks) == 2
    assert chunks[0].choices[0].message["content"] == "Hi"
    assert chunks[1].choices[0].message["content"] == " there!"
    assert chunks[0].provider == "mistral"


@patch("httpx.get")
def test_mistral_list_models(mock_get, mistral_provider):
    """Test retrieving models list from Mistral."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "mistral-large-latest",
                "object": "model",
                "owned_by": "mistral",
                "max_context_length": 32768
            }
        ]
    }
    mock_get.return_value = mock_response

    models = mistral_provider.list_models()
    assert len(models) == 1
    assert models[0].id == "mistral-large-latest"
    assert models[0].context_length == 32768
    assert models[0].owned_by == "mistral"
