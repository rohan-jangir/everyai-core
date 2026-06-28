"""Providers registry for everyai-core.

This module houses the registry of all built-in and user-defined LLM provider
classes, mapping name identifiers (e.g., 'groq') to their class implementations.
"""

from typing import Type
from everyai_core.providers.base import BaseProvider
from everyai_core.providers.groq import GroqProvider
from everyai_core.providers.openrouter import OpenRouterProvider
from everyai_core.providers.huggingface import HuggingFaceProvider
from everyai_core.providers.cerebras import CerebrasProvider
from everyai_core.providers.mistral import MistralProvider
from everyai_core.providers.cloudflare import CloudflareProvider
from everyai_core.providers.nvidia import NvidiaProvider

# Global registry dictionary mapping lowercased provider names to their classes
_registry: dict[str, Type[BaseProvider]] = {
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "huggingface": HuggingFaceProvider,
    "cerebras": CerebrasProvider,
    "mistral": MistralProvider,
    "cloudflare": CloudflareProvider,
    "nvidia": NvidiaProvider,
}


def get_provider_class(name: str) -> Type[BaseProvider]:
    """Retrieve the provider class associated with a specific name.

    Args:
        name: The name identifier of the provider (case-insensitive).

    Returns:
        The provider class subclassing BaseProvider.

    Raises:
        ValueError: If the provider name is not registered.
    """
    provider_key = name.strip().lower()
    if provider_key not in _registry:
        raise ValueError(
            f"Unsupported provider: '{name}'. "
            f"Currently supported: {list_providers()}"
        )
    return _registry[provider_key]


def register_provider(name: str, provider_cls: Type[BaseProvider]) -> None:
    """Register a custom provider class into the EveryAI ecosystem.

    Args:
        name: Unique name identifier for the provider.
        provider_cls: The provider class inheriting from BaseProvider.
    """
    if not issubclass(provider_cls, BaseProvider):
        raise TypeError("Provider class must inherit from BaseProvider")
    
    provider_key = name.strip().lower()
    _registry[provider_key] = provider_cls


def list_providers() -> list[str]:
    """Get a list of all registered provider names.

    Returns:
        A list of strings representing the supported providers.
    """
    return list(_registry.keys())


__all__ = [
    "BaseProvider",
    "GroqProvider",
    "OpenRouterProvider",
    "HuggingFaceProvider",
    "get_provider_class",
    "register_provider",
    "list_providers",
]
