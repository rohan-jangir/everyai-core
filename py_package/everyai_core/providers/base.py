"""Abstract Base Class for LLM providers.

All platforms (e.g. Groq, OpenRouter, HuggingFace) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Generator
from everyai_core.types import ChatCompletionResponse, ModelInfo


class BaseProvider(ABC):
    """Abstract Base Class defining the contract for all LLM providers."""

    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        """Initialize the provider with API credentials and custom configuration.

        Args:
            api_key: The API key for the provider's service.
            base_url: Optional override URL for API calls.
            **kwargs: Additional provider-specific configuration settings.
        """
        self.api_key = api_key
        self.base_url = base_url
        self.extra_config = kwargs

    @abstractmethod
    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Send a chat completion request to the provider.

        Args:
            model: The ID/name of the model to query.
            messages: A list of messages (e.g. [{"role": "user", "content": "..."}]).
            temperature: Sampling temperature (default: 0.7).
            max_tokens: Maximum number of tokens to generate.
            stream: Whether to stream the response.
            **kwargs: Provider-specific overrides (e.g., top_p, penalty terms).

        Returns:
            A ChatCompletionResponse instance if stream=False,
            or a generator yielding ChatCompletionResponse if stream=True.
        """
        pass

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """List available models for this provider's API key.

        Returns:
            A list of ModelInfo objects.
        """
        pass
