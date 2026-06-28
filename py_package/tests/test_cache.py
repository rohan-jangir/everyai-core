"""Unit tests for the local response cache.

Asserts SQLite response cache lookup, storage, hashing, and client integration.
"""

import pytest
from pathlib import Path
from everyai_core import EveryAI
from everyai_core.cache import RequestCache
from everyai_core.types import ChatCompletionResponse, ChatCompletionChoice, UsageInfo
from everyai_core.providers import register_provider, BaseProvider


class MockCacheProvider(BaseProvider):
    """Mock provider to verify cache hits vs misses."""
    call_count = 0

    def chat(self, model, messages, temperature=0.7, max_tokens=None, stream=False, **kwargs):
        MockCacheProvider.call_count += 1
        return ChatCompletionResponse(
            id=f"mock-completion-{MockCacheProvider.call_count}",
            object="chat.completion",
            created=12345,
            model=model,
            choices=[ChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": f"Response number {MockCacheProvider.call_count}"}
            )],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="groq"
        )

    def list_models(self):
        return []


@pytest.fixture
def temp_cache_db(tmp_path):
    """Fixture providing a temporary SQLite cache database path."""
    db_file = tmp_path / "cache.db"
    return db_file


def test_cache_set_and_get(temp_cache_db):
    """Test basic Cache set and get operations."""
    cache = RequestCache(db_path=temp_cache_db)
    
    messages = [{"role": "user", "content": "Hello!"}]
    response = ChatCompletionResponse(
        id="test-id",
        object="chat.completion",
        created=1000,
        model="test-model",
        choices=[ChatCompletionChoice(index=0, message={"role": "assistant", "content": "Hi there!"})],
        usage=UsageInfo(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        provider="groq"
    )

    # Initially a cache miss
    cached = cache.get(messages, "groq", "test-model", 0.7, None)
    assert cached is None

    # Set cache entry
    cache.set(messages, "groq", "test-model", 0.7, None, response)

    # Now it should be a cache hit
    cached = cache.get(messages, "groq", "test-model", 0.7, None)
    assert cached is not None
    assert cached.id == "test-id"
    assert cached.choices[0].message["content"] == "Hi there!"
    assert cached.usage.total_tokens == 20
    assert cached.provider == "groq"

    # Different temperature should be a cache miss
    assert cache.get(messages, "groq", "test-model", 0.8, None) is None


def test_cache_client_integration(temp_cache_db, tmp_path):
    """Test EveryAI client cache hit intercepts network request and logs telemetry."""
    register_provider("mock_cache_prov", MockCacheProvider)
    
    usage_db = tmp_path / "usage.db"
    client = EveryAI(
        api_keys={"mock_cache_prov": "mock_key"},
        db_path=usage_db,
        cache=True,
        cache_path=temp_cache_db
    )
    
    # Reset mock counter
    MockCacheProvider.call_count = 0
    messages = [{"role": "user", "content": "Cache test message"}]

    # 1. First call -> Cache Miss
    res1 = client.chat(
        provider="mock_cache_prov",
        model="mock-model",
        messages=messages,
        temperature=0.7
    )
    assert MockCacheProvider.call_count == 1
    assert res1.choices[0].message["content"] == "Response number 1"

    # Verify telemetry logs: 1 success log with 15 tokens
    summary1 = client.tracker.get_summary()
    assert summary1["total_calls"] == 1
    assert summary1["total_tokens"] == 15
    assert summary1["cache_hits_total"] == 0

    # 2. Second call -> Cache Hit
    res2 = client.chat(
        provider="mock_cache_prov",
        model="mock-model",
        messages=messages,
        temperature=0.7
    )
    # Call count should still be 1 (never hit network)
    assert MockCacheProvider.call_count == 1
    assert res2.choices[0].message["content"] == "Response number 1"

    # Verify telemetry logs updated: 2 total calls, 1 cache hit, tokens saved = 15, total tokens consumed remains 15
    summary2 = client.tracker.get_summary()
    assert summary2["total_calls"] == 2
    assert summary2["cache_hits_total"] == 1
    assert summary2["tokens_saved_total"] == 15
    assert summary2["total_tokens"] == 15  # Total tokens consumed did not increase
