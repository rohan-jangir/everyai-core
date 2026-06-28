"""Unit tests for the Cloudflare AI provider implementation.

Mocks the httpx REST requests to verify chat completion, streaming, and model listing.
"""

import pytest
from unittest.mock import MagicMock, patch
from everyai_core.providers.cloudflare import CloudflareProvider
from everyai_core.types import ChatCompletionResponse
from everyai_core.exceptions import ConfigurationError


@pytest.fixture
def cloudflare_provider():
    return CloudflareProvider(api_key="cf_test_token", account_id="cf_test_acc")


def test_cloudflare_requires_account_id():
    """Test that CloudflareProvider raises ConfigurationError if account_id is not set."""
    prov = CloudflareProvider(api_key="cf_test_token")
    with pytest.raises(ConfigurationError) as exc:
        prov.chat(model="@cf/meta/llama-3-8b-instruct", messages=[{"role": "user", "content": "hi"}])
    assert "account_id" in str(exc.value)


@patch("httpx.post")
def test_cloudflare_chat_non_streaming(mock_post, cloudflare_provider):
    """Test successful non-streaming chat request to Cloudflare."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "response": "Hello from Cloudflare!"
        },
        "success": True,
        "errors": [],
        "messages": []
    }
    mock_post.return_value = mock_response

    response = cloudflare_provider.chat(
        model="@cf/meta/llama-3-8b-instruct",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7
    )

    assert isinstance(response, ChatCompletionResponse)
    assert response.choices[0].message["content"] == "Hello from Cloudflare!"
    assert response.provider == "cloudflare"

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.cloudflare.com/client/v4/accounts/cf_test_acc/ai/run/@cf/meta/llama-3-8b-instruct"
    assert kwargs["headers"]["Authorization"] == "Bearer cf_test_token"
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "hi"}]


@patch("httpx.Client")
def test_cloudflare_chat_streaming(mock_client_cls, cloudflare_provider):
    """Test successful streaming chat request to Cloudflare."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.__enter__.return_value = mock_client

    mock_stream_ctx = MagicMock()
    mock_client.stream.return_value = mock_stream_ctx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        b'data: {"response": "Hi"}',
        b'data: {"response": " cloudflare"}',
        b'data: [DONE]'
    ]
    mock_stream_ctx.__enter__.return_value = mock_response

    generator = cloudflare_provider.chat(
        model="@cf/meta/llama-3-8b-instruct",
        messages=[{"role": "user", "content": "hi"}],
        stream=True
    )

    chunks = list(generator)
    assert len(chunks) == 2
    assert chunks[0].choices[0].message["content"] == "Hi"
    assert chunks[1].choices[0].message["content"] == " cloudflare"
    assert chunks[0].provider == "cloudflare"


def test_cloudflare_list_models(cloudflare_provider):
    """Test retrieving preset models list from Cloudflare."""
    models = cloudflare_provider.list_models()
    assert len(models) > 0
    assert models[0].id == "@cf/meta/llama-3-8b-instruct"
    assert models[0].owned_by == "cloudflare"
