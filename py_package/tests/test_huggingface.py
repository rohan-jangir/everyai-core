"""Unit tests for the HuggingFace provider implementation.

Mocks HTTP REST requests for cloud Inference API execution,
and mocks transformers/torch libraries for local execution tests.
"""

import sys
import pytest
from unittest.mock import MagicMock, patch
from everyai_core.providers.huggingface import HuggingFaceProvider
from everyai_core.exceptions import ConfigurationError
from everyai_core.types import ChatCompletionResponse


@pytest.fixture
def hf_provider():
    # Clear local cache before test runs to ensure independent loads
    HuggingFaceProvider._local_cache.clear()
    return HuggingFaceProvider(api_key="hf_test_key")


# ==========================================
# Cloud branch tests
# ==========================================

@patch("httpx.post")
def test_hf_chat_cloud_non_streaming(mock_post, hf_provider):
    """Test successful serverless cloud Inference API request."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "chatcmpl-hf-123",
        "object": "chat.completion",
        "created": 1600000000,
        "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from HuggingFace Cloud!"},
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

    response = hf_provider.chat(
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.7,
        local=False
    )

    assert isinstance(response, ChatCompletionResponse)
    assert response.id == "chatcmpl-hf-123"
    assert response.choices[0].message["content"] == "Hello from HuggingFace Cloud!"
    assert response.usage.total_tokens == 18
    assert response.provider == "huggingface"

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api-inference.huggingface.co/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer hf_test_key"


@patch("httpx.Client")
def test_hf_chat_cloud_streaming(mock_client_cls, hf_provider):
    """Test successful streaming cloud Inference API request."""
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

    generator = hf_provider.chat(
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
        local=False
    )

    chunks = list(generator)
    assert len(chunks) == 2
    assert chunks[0].choices[0].message["content"] == "Hi"
    assert chunks[1].choices[0].message["content"] == " there!"


# ==========================================
# Local branch tests
# ==========================================

def test_hf_chat_local_missing_dependencies(hf_provider):
    """Assert ConfigurationError is raised with suggestions if dependencies are missing."""
    # Temporarily hide torch and transformers from imports
    with patch.dict("sys.modules", {"torch": None, "transformers": None}):
        with pytest.raises(ConfigurationError) as exc_info:
            hf_provider.chat(
                model="gpt2",
                messages=[{"role": "user", "content": "hi"}],
                local=True
            )
        assert "Local inference requires 'transformers' and 'torch' packages" in str(exc_info.value)
        assert "pip install transformers torch" in str(exc_info.value)


def test_hf_chat_local_success(hf_provider):
    """Test local transformers inference execution is mocked successfully."""
    # Mock torch and transformers packages
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    
    mock_tokenizer = MagicMock()
    mock_tokenizer.apply_chat_template.return_value = "<mocked prompt>"
    mock_tokenizer.decode.return_value = "Hello from local model!"
    
    # Mock return values for shapes (e.g. inputs.input_ids.shape[1] = prompt_tokens)
    mock_inputs = MagicMock()
    mock_inputs.input_ids.shape = [1, 5]  # shape is (batch_size, seq_len), shape[1] = 5
    mock_inputs.to.return_value = mock_inputs
    mock_tokenizer.return_value = mock_inputs

    mock_model = MagicMock()
    mock_model.generate.return_value = [[0] * 12] # outputs, prompt_len (5) + completion_len (7) = 12
    
    mock_transformers = MagicMock()
    mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer
    mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

    # Patch sys.modules to return our mocks
    sys_modules_patch = {
        "torch": mock_torch,
        "transformers": mock_transformers,
        "transformers.AutoTokenizer": mock_transformers.AutoTokenizer,
        "transformers.AutoModelForCausalLM": mock_transformers.AutoModelForCausalLM
    }

    with patch.dict("sys.modules", sys_modules_patch):
        response = hf_provider.chat(
            model="gpt2",
            messages=[{"role": "user", "content": "hi"}],
            local=True,
            temperature=0.7
        )

        assert isinstance(response, ChatCompletionResponse)
        assert response.id == "chatcmpl-local-hf"
        assert response.choices[0].message["content"] == "Hello from local model!"
        assert response.usage.prompt_tokens == 5
        assert response.usage.completion_tokens == 7  # 12 - 5
        assert response.usage.total_tokens == 12
        assert response.provider == "huggingface"

        # Verify lazy load cache loaded the model in memory
        assert "gpt2" in HuggingFaceProvider._local_cache
        assert HuggingFaceProvider._local_cache["gpt2"][0] == mock_tokenizer
        assert HuggingFaceProvider._local_cache["gpt2"][1] == mock_model
