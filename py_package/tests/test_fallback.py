"""Unit tests for the EveryAI automatic fallback switching system.

Verifies failover routing, loop-back pass settings, and multi-key configurations.
"""

import pytest
from everyai_core import EveryAI, EveryAIError
from everyai_core.exceptions import RateLimitError
from everyai_core.providers import register_provider, BaseProvider
from everyai_core.types import ChatCompletionResponse, ModelInfo


class FallbackMockProvider(BaseProvider):
    """Mock provider with selective failure triggers based on key/model parameters."""

    def chat(self, model, messages, temperature=0.7, max_tokens=None, stream=False, **kwargs):
        # Trigger rate limits on request
        if "rate-limit" in model:
            raise RateLimitError("Rate limit exceeded", provider="fallbackmock")
            
        # Fail if unauthorized API key is passed
        if self.api_key == "unauthorized_key":
            raise RateLimitError("Unauthorized API Key limit reached", provider="fallbackmock")

        # Successful completion mock response
        from everyai_core.types import UsageInfo, ChatCompletionChoice
        return ChatCompletionResponse(
            id="mock-success-id",
            object="chat.completion",
            created=1234567,
            model=model,
            choices=[ChatCompletionChoice(index=0, message={"role": "assistant", "content": "Success content"})],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        )

    def list_models(self):
        return [ModelInfo(id="mock-model", name="Mock Model")]


def test_fallback_switching_success(tmp_path):
    """Test switching from a failing configuration to a successful alternate provider."""
    register_provider("fallbackmock", FallbackMockProvider)
    db_file = tmp_path / "test_fallback_switch.db"

    fallback_chain = [
        {"provider": "fallbackmock", "model": "gpt-4-rate-limit"},  # Will fail
        {"provider": "fallbackmock", "model": "gpt-4-success"}      # Will succeed
    ]

    client = EveryAI(
        api_keys={"fallbackmock": "good_key"},
        fallback_chain=fallback_chain,
        db_path=db_file
    )

    # Calling chat without provider/model triggers the client default fallback chain
    response = client.chat(messages=[{"role": "user", "content": "hi"}])
    assert response.id == "mock-success-id"
    assert response.model == "gpt-4-success"

    # Verify that telemetry logged both calls: one rate_limit and one success
    logs = client.tracker.get_logs()
    assert len(logs) == 2
    assert logs[0]["status"] == "success"
    assert logs[1]["status"] == "rate_limit"


def test_fallback_per_request_override(tmp_path):
    """Test overriding client-level defaults with per-request fallback chains."""
    register_provider("fallbackmock", FallbackMockProvider)
    db_file = tmp_path / "test_fallback_override.db"

    default_chain = [
        {"provider": "fallbackmock", "model": "gpt-4-rate-limit"}  # Will fail
    ]
    request_chain = [
        {"provider": "fallbackmock", "model": "gpt-4-rate-limit"},  # Will fail
        {"provider": "fallbackmock", "model": "gpt-4-success"}      # Will succeed
    ]

    client = EveryAI(
        api_keys={"fallbackmock": "good_key"},
        fallback_chain=default_chain,
        db_path=db_file
    )

    # Calling with explicit request_chain override
    response = client.chat(fallback_chain=request_chain, messages=[{"role": "user", "content": "hi"}])
    assert response.id == "mock-success-id"


def test_fallback_multi_pass_loop_raises(tmp_path):
    """Test that max_passes retry limit triggers looping and finally raises EveryAIError."""
    register_provider("fallbackmock", FallbackMockProvider)
    db_file = tmp_path / "test_fallback_loop.db"

    fallback_chain = [
        {"provider": "fallbackmock", "model": "gpt-4-rate-limit-1"},
        {"provider": "fallbackmock", "model": "gpt-4-rate-limit-2"}
    ]

    client = EveryAI(
        api_keys={"fallbackmock": "good_key"},
        fallback_chain=fallback_chain,
        db_path=db_file
    )

    with pytest.raises(EveryAIError) as exc_info:
        client.chat(messages=[{"role": "user", "content": "hi"}], max_passes=2)

    err_text = str(exc_info.value)
    assert "Inference failed. All fallback configurations in the chain failed after 2 passes." in err_text
    # Should list both configurations for Pass 1 and Pass 2 (4 failures total)
    assert "Pass 1 Config 0" in err_text
    assert "Pass 1 Config 1" in err_text
    assert "Pass 2 Config 0" in err_text
    assert "Pass 2 Config 1" in err_text

    # Database should record 4 failures
    assert len(client.tracker.get_logs()) == 4


def test_fallback_multiple_api_keys(tmp_path):
    """Test that multiple accounts/keys for the same provider are isolated in cache."""
    register_provider("fallbackmock", FallbackMockProvider)
    db_file = tmp_path / "test_fallback_keys.db"

    fallback_chain = [
        # Uses unauthorized key -> fails
        {"provider": "fallbackmock", "model": "gpt-4-model", "api_key": "unauthorized_key"},
        # Uses good authorized key -> succeeds
        {"provider": "fallbackmock", "model": "gpt-4-model", "api_key": "authorized_key"}
    ]

    client = EveryAI(db_path=db_file)

    # Calling chat will attempt both keys in order
    response = client.chat(fallback_chain=fallback_chain, messages=[{"role": "user", "content": "hi"}])
    assert response.id == "mock-success-id"

    # Database check: 1 rate_limit and 1 success logged
    logs = client.tracker.get_logs()
    assert len(logs) == 2
    assert logs[0]["status"] == "success"
    assert logs[1]["status"] == "rate_limit"
