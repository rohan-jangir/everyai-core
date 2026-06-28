"""Unit tests for the EveryAI telemetry tracker and client instrumentation.

Verifies correct logging to SQLite, stats aggregation, and client call wrapping.
"""

import os
import pytest
from everyai_core import EveryAI, ConfigurationError
from everyai_core.tracker import UsageTracker
from everyai_core.exceptions import RateLimitError
from everyai_core.providers import register_provider, BaseProvider
from everyai_core.types import ChatCompletionResponse, ModelInfo


def test_tracker_raw_db_operations(tmp_path):
    """Test raw SQL logging, summaries, and clears using a temporary database file."""
    db_file = tmp_path / "test_usage.db"
    tracker = UsageTracker(db_path=db_file)

    # Database starts empty
    summary = tracker.get_summary()
    assert summary["total_calls"] == 0
    assert len(tracker.get_logs()) == 0

    # Log successful call
    tracker.log_call(
        provider="groq",
        model="llama3-8b",
        prompt_tokens=10,
        completion_tokens=20,
        status="success"
    )

    # Log rate limit call
    tracker.log_call(
        provider="groq",
        model="llama3-8b",
        prompt_tokens=None,
        completion_tokens=None,
        status="rate_limit",
        error_message="Rate limit exceeded. Try again in 2s."
    )

    # Log openrouter call
    tracker.log_call(
        provider="openrouter",
        model="claude-3-haiku",
        prompt_tokens=5,
        completion_tokens=15,
        status="success"
    )

    # Verify summary aggregations
    summary = tracker.get_summary()
    assert summary["total_calls"] == 3
    assert summary["total_prompt_tokens"] == 15   # 10 + 5
    assert summary["total_completion_tokens"] == 35 # 20 + 15
    assert summary["total_tokens"] == 50
    assert summary["rate_limits_total"] == 1

    # Check breakdown by provider
    by_provider = summary["by_provider"]
    assert "groq" in by_provider
    assert "openrouter" in by_provider
    assert by_provider["groq"]["calls"] == 2
    assert by_provider["groq"]["rate_limits"] == 1
    assert by_provider["openrouter"]["total_tokens"] == 20

    # Verify log fetching
    logs = tracker.get_logs()
    assert len(logs) == 3
    assert logs[0]["provider"] == "openrouter"  # Most recent first
    assert logs[1]["status"] == "rate_limit"
    assert logs[1]["error_message"] == "Rate limit exceeded. Try again in 2s."

    # Clear logs and verify truncation
    tracker.clear_logs()
    assert tracker.get_summary()["total_calls"] == 0
    assert len(tracker.get_logs()) == 0


class MockTrackingProvider(BaseProvider):
    """Mock provider to check client integration tracking."""

    def chat(self, model, messages, temperature=0.7, max_tokens=None, stream=False, **kwargs):
        if model == "trigger-rate-limit":
            raise RateLimitError("Rate limit hit", provider="mocktracking")
        
        from everyai_core.types import UsageInfo, ChatCompletionChoice
        return ChatCompletionResponse(
            id="mock-id",
            object="chat.completion",
            created=12345,
            model=model,
            choices=[ChatCompletionChoice(index=0, message={"role": "assistant", "content": "mock content"})],
            usage=UsageInfo(prompt_tokens=50, completion_tokens=100, total_tokens=150)
        )

    def list_models(self):
        return [ModelInfo(id="mock-model", name="Mock Model")]


def test_client_tracking_integration(tmp_path):
    """Test that calling EveryAI client methods automatically logs requests to the tracker."""
    db_file = tmp_path / "test_client_usage.db"
    
    # Register the mock provider class
    register_provider("mocktracking", MockTrackingProvider)
    
    # Initialize client with manual key and custom db path
    client = EveryAI(api_keys={"mocktracking": "mock-key"}, db_path=db_file)
    
    # Verify DB starts empty
    assert client.tracker.get_summary()["total_calls"] == 0
    
    # Run successful chat call
    res = client.chat(
        provider="mocktracking",
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}]
    )
    assert res.id == "mock-id"
    
    # Run rate limit chat call
    with pytest.raises(RateLimitError):
        client.chat(
            provider="mocktracking",
            model="trigger-rate-limit",
            messages=[{"role": "user", "content": "hello"}]
        )
        
    # Check that both calls were recorded in DB
    summary = client.tracker.get_summary()
    assert summary["total_calls"] == 2
    assert summary["total_tokens"] == 150
    assert summary["rate_limits_total"] == 1
    
    # Check logs
    logs = client.tracker.get_logs()
    assert logs[0]["status"] == "rate_limit"
    assert logs[0]["error_message"] == "[MOCKTRACKING API Error]: Rate limit hit"
    assert logs[1]["status"] == "success"
    assert logs[1]["total_tokens"] == 150
