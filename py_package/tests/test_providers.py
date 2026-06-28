"""Unit tests for EveryAI provider registration and interface compliance.

Ensures BaseProvider interface contract enforcement and dynamic extensibility.
"""

import pytest
from typing import Any, Generator
from everyai_core.providers import (
    BaseProvider,
    register_provider,
    get_provider_class,
    list_providers,
)
from everyai_core.types import ChatCompletionResponse, ModelInfo


class DummyProvider(BaseProvider):
    """A dummy provider implementation for registration testing."""

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        return ChatCompletionResponse(
            id="dummy-id",
            object="chat.completion",
            created=123456,
            model=model,
            choices=[]
        )

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="dummy-model", name="Dummy Model")]


def test_dynamic_provider_registration():
    """Test registering a custom provider and verifying it can be instantiated."""
    # Ensure it's not currently listed
    assert "dummy" not in list_providers()
    
    # Register the dummy
    register_provider("dummy", DummyProvider)
    
    # Verify it is listed and class is retrievable
    assert "dummy" in list_providers()
    provider_cls = get_provider_class("dummy")
    assert provider_cls == DummyProvider
    
    # Instantiate and test methods
    instance = provider_cls(api_key="test-key")
    res = instance.chat("dummy-model", [{"role": "user", "content": "hi"}])
    assert res.id == "dummy-id"
    assert len(instance.list_models()) == 1


def test_invalid_provider_registration():
    """Test that registering a class not subclassing BaseProvider raises TypeError."""
    class BadProvider:
        pass
        
    with pytest.raises(TypeError) as exc_info:
        register_provider("bad", BadProvider)  # type: ignore
    assert "Provider class must inherit from BaseProvider" in str(exc_info.value)


def test_provider_instantiation():
    """Test that built-in provider classes can be instantiated successfully."""
    for provider_name in ["groq", "openrouter", "huggingface"]:
        cls = get_provider_class(provider_name)
        instance = cls(api_key="mock-key")
        assert instance.api_key == "mock-key"
        assert instance.base_url is None
